#!/usr/bin/env python3
"""Add deterministic, site-only fields to qri JSONL records."""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
from pathlib import Path
import sys
from typing import Any


INFO = {
    "ror:04tfhh831": {
        "path": "",
        "label": "Center for Open Neuroscience",
        "image": "img/con-logo.svg",
    },
    "xyzrins:persons/yaroslav-halchenko": {
        "path": "persons/yaroslav-halchenko",
        "label": "Yaroslav O. Halchenko",
        "image": "img/yaroslav-halchenko.jpg",
    },
    "xyzrins:projects/datalad": {
        "path": "projects/datalad",
        "label": "DataLad",
        "image": "img/datalad-logo.png",
    },
    "https://doi.org/10.21105/joss.03262": {
        "path": "publications/datalad-joss-2021",
        "label": "DataLad JOSS article",
    },
    "xyzrins:instruments/datalad": {
        "path": "instruments/datalad",
        "label": "DataLad software",
        "image": "img/datalad-logo.png",
    },
}

ROLE_LABELS = {
    "marcrel:aut": "Selected author",
    "marcrel:led": "Lead",
}

RELATION_LABELS = {
    "dcterms:contributor": "Selected project lead",
    "foaf:homepage": "Project homepage",
    "schema:about": "Related project",
    "schema:subjectOf": "Related publication",
}


def object_pid(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        pid = value.get("pid")
        return pid if isinstance(pid, str) else None
    return None


def object_label(value: Any, pid: str) -> str:
    if isinstance(value, dict):
        for key in ("display_label", "formatted_name", "title", "name"):
            if value.get(key):
                return str(value[key])
        if value.get("given_name") and value.get("family_name"):
            return f"{value['given_name']} {value['family_name']}"
    return str(INFO.get(pid, {}).get("label", pid))


def relative_href(current_pid: str, target: str) -> str:
    if target not in INFO:
        return target if target.startswith(("http://", "https://")) else ""
    current_path = str(INFO[current_pid]["path"] or ".")
    target_path = str(INFO[target]["path"] or ".")
    relative = posixpath.relpath(target_path, current_path)
    return "./" if relative == "." else relative.rstrip("/") + "/"


def linked(current_pid: str, value: Any) -> dict[str, str] | None:
    pid = object_pid(value)
    if not pid:
        return None
    return {
        "pid": pid,
        "label": object_label(value, pid),
        "href": relative_href(current_pid, pid),
    }


def relation_label(predicate: str, target_pid: str) -> str:
    if predicate == "dcterms:relation":
        if target_pid.startswith("xyzrins:instruments/"):
            return "Software output"
        if target_pid.startswith("xyzrins:projects/"):
            return "Related project"
        if target_pid.startswith("xyzrins:persons/"):
            return "Person"
        if target_pid.startswith("ror:"):
            return "Organization"
    return RELATION_LABELS.get(predicate, predicate)


def enrich(record: dict[str, Any], output_root: Path) -> dict[str, Any]:
    pid = record.get("pid")
    if pid not in INFO:
        raise ValueError(f"No reviewed projection path for record {pid!r}")
    source_fingerprint = hashlib.sha256(
        json.dumps(record, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    info = INFO[pid]
    page_path = str(info["path"])
    record["page_path"] = page_path
    record["output_path"] = str(
        output_root / page_path / "index.md"
        if page_path
        else output_root / "_index.md"
    )
    record["page_title"] = str(
        record.get("display_label")
        or record.get("formatted_name")
        or record.get("title")
        or record.get("name")
        or info["label"]
    )
    record["metadata_fingerprint"] = source_fingerprint
    if image := info.get("image"):
        record["depiction_shortcode"] = (
            '{{< asset-image src="'
            + str(image)
            + '" alt="'
            + str(info["label"])
            + '" >}}'
        )

    associations = []
    for association in record.get("associated_with", []):
        relation = linked(pid, association.get("object"))
        if not relation:
            continue
        relation["roles"] = ", ".join(
            ROLE_LABELS.get(object_pid(role) or str(role), object_pid(role) or str(role))
            for role in association.get("roles", [])
        )
        associations.append(relation)
    for attribute in record.get("attributes", []):
        predicate = attribute.get("predicate")
        target = linked(pid, attribute.get("value"))
        if not target:
            continue
        if target["pid"].startswith("ror:") and predicate == "dcterms:relation":
            target["roles"] = "Organization"
            associations.append(target)
        elif (
            target["pid"].startswith("xyzrins:persons/")
            and predicate == "dcterms:contributor"
        ):
            target["roles"] = "Selected project lead"
            associations.append(target)
    record["x_associations"] = associations

    relations = []
    for attribute in record.get("attributes", []):
        predicate = attribute.get("predicate")
        value = attribute.get("value")
        if not isinstance(value, str):
            continue
        if (
            predicate == "dcterms:contributor"
            or predicate == "dcterms:relation"
            and value.startswith("ror:")
        ):
            continue
        target = linked(pid, value) or {
            "pid": value,
            "label": value,
            "href": value if value.startswith(("http://", "https://")) else "",
        }
        target["relation"] = relation_label(str(predicate), target["pid"])
        relations.append(target)
    record["x_relations"] = relations

    authors = []
    for attribution in record.get("attributed_to", []):
        author = linked(pid, attribution.get("object"))
        if author:
            authors.append(author)
    for attribute in record.get("attributes", []):
        if attribute.get("predicate") != "dcterms:creator":
            continue
        author = linked(pid, attribute.get("value"))
        if author and author not in authors:
            authors.append(author)
    record["x_authors"] = authors

    projects = []
    for project in record.get("projects", []):
        relation = linked(pid, project)
        if relation:
            projects.append(relation)
    for attribute in record.get("attributes", []):
        if attribute.get("predicate") not in {"schema:about", "dcterms:relation"}:
            continue
        project = linked(pid, attribute.get("value"))
        if (
            project
            and project["pid"].startswith("xyzrins:projects/")
            and project not in projects
        ):
            projects.append(project)
    record["x_projects"] = [project for project in projects if project]

    people = []
    for attribute in record.get("attributes", []):
        if attribute.get("predicate") != "schema:member":
            continue
        person = linked(pid, attribute.get("value"))
        if person and person not in people:
            people.append(person)
    for project in record.get("projects", []):
        if not isinstance(project, dict):
            continue
        for association in project.get("associated_with", []):
            target_pid = object_pid(association.get("object"))
            if target_pid and target_pid.startswith("xyzrins:persons/"):
                person = linked(pid, association.get("object"))
                if person and person not in people:
                    people.append(person)
    record["x_people"] = people
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    for line in sys.stdin:
        if not line.strip():
            continue
        record = json.loads(line)
        print(json.dumps(enrich(record, args.output_root), ensure_ascii=False))


if __name__ == "__main__":
    main()
