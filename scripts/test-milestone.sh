#!/usr/bin/env bash
set -euo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repository_root"
test_base_url=https://example.invalid/orinoco-lite-preview/

BASE_URL=$test_base_url BUILD_DIR=build scripts/build.sh
BASE_URL=$test_base_url BUILD_DIR=build-repeat scripts/build.sh
diff -u build/site-manifest.sha256 build-repeat/site-manifest.sha256

metadata_copy=build-test-metadata
python3 - "$metadata_copy" <<'PY'
from pathlib import Path
import shutil
import sys

target = Path(sys.argv[1]).resolve()
repository = Path.cwd().resolve()
if target.parent != repository or not target.name.startswith("build-"):
    raise SystemExit(f"unsafe test metadata path: {target}")
if target.exists():
    shutil.rmtree(target)
shutil.copytree(repository / "metadata", target)
PY
trap 'python3 - "$metadata_copy" <<'"'"'PY'"'"'
from pathlib import Path
import shutil
import sys
path = Path(sys.argv[1]).resolve()
if path.parent == Path.cwd().resolve() and path.name.startswith("build-"):
    shutil.rmtree(path, ignore_errors=True)
PY' EXIT

uv run python - "$metadata_copy/records/XYZProject/datalad.yaml" <<'PY'
from pathlib import Path
import sys
import yaml

path = Path(sys.argv[1])
record = yaml.safe_load(path.read_text(encoding="utf-8"))
record["title"] = "DataLad metadata-change proof"
record["display_label"] = record["title"]
path.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")
PY

BASE_URL=$test_base_url \
  BUILD_DIR=build-mutated \
  METADATA_ROOT=$metadata_copy \
  scripts/build.sh
grep -q 'DataLad metadata-change proof' \
  build-mutated/site/projects/datalad/index.html
if cmp -s \
  build/site/projects/datalad/index.html \
  build-mutated/site/projects/datalad/index.html; then
  echo "Metadata mutation did not change its preview page" >&2
  exit 1
fi

echo "Milestone contract: deterministic build and metadata propagation verified"
