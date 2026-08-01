#!/usr/bin/env bash
set -euo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repository_root"
test_base_url=https://example.invalid/orinoco-lite-preview/

BASE_URL=$test_base_url BUILD_DIR=build scripts/build.sh
BASE_URL=$test_base_url BUILD_DIR=build-repeat scripts/build.sh
diff -u build/site-manifest.sha256 build-repeat/site-manifest.sha256

metadata_cases=$(mktemp -d ./build-test-metadata.XXXXXX)
cleanup_cases() {
  python - "$metadata_cases" <<'PY'
from pathlib import Path
import shutil
import sys

path = Path(sys.argv[1]).resolve()
repository = Path.cwd().resolve()
if path.parent == repository and path.name.startswith("build-test-metadata."):
    shutil.rmtree(path, ignore_errors=True)
PY
}
trap cleanup_cases EXIT

python - "$metadata_cases" <<'PY'
from pathlib import Path
import shutil
import sys

import yaml

root = Path(sys.argv[1])
source = Path("metadata")
for name in ("sixth", "schema-invalid", "dangling-doi"):
    shutil.copytree(source, root / name)

sixth = {
    "pid": "xyzrins:projects/metadata-only-sixth",
    "title": "Metadata-only sixth project",
    "display_label": "Metadata-only sixth project",
    "description": "A test record added without changing routes, templates, indexes, or graph code.",
    "attributes": [
        {
            "schema_type": "dlthings:AttributeSpecification",
            "predicate": "dcterms:contributor",
            "value": "xyzrins:persons/yaroslav-halchenko",
        }
    ],
}
sixth_path = root / "sixth/records/XYZProject/nested/metadata-only-sixth.yaml"
sixth_path.parent.mkdir()
sixth_path.write_text(
    yaml.safe_dump(sixth, sort_keys=False), encoding="utf-8"
)

invalid_path = root / "schema-invalid/records/XYZProject/datalad.yaml"
invalid = yaml.safe_load(invalid_path.read_text(encoding="utf-8"))
invalid["attributes"][0]["unknown_nested_milestone_field"] = True
nested_invalid_path = invalid_path.parent / "nested/datalad.yaml"
nested_invalid_path.parent.mkdir()
nested_invalid_path.write_text(
    yaml.safe_dump(invalid, sort_keys=False), encoding="utf-8"
)
invalid_path.unlink()

dangling_path = root / "dangling-doi/records/XYZProject/datalad.yaml"
dangling = yaml.safe_load(dangling_path.read_text(encoding="utf-8"))
next(
    item
    for item in dangling["attributes"]
    if item.get("predicate") == "schema:subjectOf"
)["value"] = "https://doi.org/10.99999/missing-milestone-publication"
dangling_path.write_text(yaml.safe_dump(dangling, sort_keys=False), encoding="utf-8")
PY

BASE_URL=$test_base_url \
  BUILD_DIR=build-sixth \
  METADATA_ROOT="$metadata_cases/sixth" \
  scripts/build.sh

python - <<'PY'
import json
from pathlib import Path

report = json.loads(Path("build-sixth/projection-report.json").read_text())
baseline = json.loads(Path("build/projection-report.json").read_text())
assert report["record_count"] == baseline["record_count"] + 1, (baseline, report)
assert report["canonical_edge_count"] == baseline["canonical_edge_count"] + 1, (
    baseline,
    report,
)
page = Path("build-sixth/site/projects/metadata-only-sixth/index.html")
assert page.is_file()
assert "Metadata-only sixth project" in page.read_text(encoding="utf-8")
graph = json.loads(Path("build-sixth/site/graph.json").read_text())
assert any(node["id"] == "xyzrins:projects/metadata-only-sixth" for node in graph["nodes"])

records = {
    record["pid"]: record
    for record in map(json.loads, Path("build/projected-records.jsonl").read_text().splitlines())
}
project = records["xyzrins:projects/datalad"]
assert project["page_ref"] == "/orinoco-lite-preview/projects/datalad/", project
assert "publications" not in project["taxonomies"], project["taxonomies"]
person_link = next(
    link
    for link in project["links_out"]
    if link["object"] == "xyzrins:persons/yaroslav-halchenko"
)
assert {assertion["predicate"] for assertion in person_link["assertions"]} == {
    "dcterms:contributor",
    "dcterms:relation",
}, person_link
baseline_graph = json.loads(Path("build/site/graph.json").read_text())
assert any(edge.get("symmetric") is True for edge in baseline_graph["edges"]), baseline_graph
PY

if cmp -s build/site-manifest.sha256 build-sixth/site-manifest.sha256; then
  echo "A canonical metadata addition did not change the preview" >&2
  exit 1
fi

if BASE_URL=$test_base_url \
  BUILD_DIR=build-schema-invalid \
  METADATA_ROOT="$metadata_cases/schema-invalid" \
  scripts/build.sh >build-schema-invalid.log 2>&1; then
  echo "A schema-invalid record passed the upstream publication gate" >&2
  exit 1
fi
grep -q "unknown_nested_milestone_field" build-schema-invalid/validation.log
grep -q "extra_forbidden" build-schema-invalid/validation.log

if BASE_URL=$test_base_url \
  BUILD_DIR=build-dangling-doi \
  METADATA_ROOT="$metadata_cases/dangling-doi" \
  scripts/build.sh >build-dangling-doi.log 2>&1; then
  echo "A dangling internal metadata link passed the projection gate" >&2
  exit 1
fi
grep -q "compatibility relationship target is absent" build-dangling-doi.log
grep -q "10.99999/missing-milestone-publication" build-dangling-doi.log

python - <<'PY'
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path("scripts").resolve()))
from prepare_build import copy_editorial_content
from project_records import project

records = [
    {
        "pid": "ror:root",
        "schema_type": "xyzri:XYZOrganization",
        "name": "Root",
        "attributes": [],
    },
    {
        "pid": "xyzrins:projects/collision",
        "schema_type": "xyzri:XYZProject",
        "title": "First",
        "attributes": [],
    },
    {
        "pid": "xyzrins:projects/COLLISION",
        "schema_type": "xyzri:XYZProject",
        "title": "Second",
        "attributes": [],
    },
]
try:
    project(records, "ror:root", Path("unused"), "https://example.invalid/")
except ValueError as error:
    assert "route collision" in str(error).lower(), error
else:
    raise AssertionError("Colliding metadata routes passed the projection gate")

with TemporaryDirectory(dir=".") as temporary:
    repository = Path(temporary) / "repository"
    rogue = repository / "content/projects/rogue/_index.md"
    rogue.parent.mkdir(parents=True)
    rogue.write_text("---\ntitle: Rogue\n---\n", encoding="utf-8")
    try:
        copy_editorial_content(repository, Path(temporary) / "output")
    except ValueError as error:
        assert "generated from validated metadata" in str(error), error
    else:
        raise AssertionError("Hand-authored entity page bypassed metadata authority")
PY

echo "Milestone contract: deterministic, metadata-extensible, and fail-closed"
