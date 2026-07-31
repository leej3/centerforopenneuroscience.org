#!/usr/bin/env python3
"""Check cross-record integrity that the upstream schema cannot express here."""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
import json
from pathlib import Path
import re
from typing import Any

import yaml


EXPECTED_TARGET_CLASSES = {
    "dcterms:contributor": {"XYZPerson"},
    "dcterms:creator": {"XYZPerson"},
    "dcterms:relation": {
        "XYZInstrument",
        "XYZOrganization",
        "XYZPerson",
        "XYZProject",
    },
    "schema:about": {"XYZProject"},
    "schema:member": {"XYZPerson"},
    "schema:memberOf": {"XYZOrganization"},
    "schema:subjectOf": {"XYZPublication"},
}

REQUIRED_RECIPROCALS = [
    (
        ("XYZOrganization", "dcterms:relation", "XYZProject"),
        ("XYZProject", "dcterms:relation", "XYZOrganization"),
    ),
    (
        ("XYZOrganization", "schema:member", "XYZPerson"),
        ("XYZPerson", "schema:memberOf", "XYZOrganization"),
    ),
    (
        ("XYZPerson", "dcterms:relation", "XYZProject"),
        ("XYZProject", "dcterms:contributor", "XYZPerson"),
    ),
    (
        ("XYZProject", "schema:subjectOf", "XYZPublication"),
        ("XYZPublication", "schema:about", "XYZProject"),
    ),
    (
        ("XYZProject", "dcterms:relation", "XYZInstrument"),
        ("XYZInstrument", "schema:about", "XYZProject"),
    ),
]

REQUIRED_CLASSES = {
    "XYZInstrument",
    "XYZOrganization",
    "XYZPerson",
    "XYZProject",
    "XYZPublication",
}

DOI = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
ISSN = re.compile(r"^\d{4}-\d{3}[\dX]$", re.IGNORECASE)


def load_records(records_root: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    records: dict[str, dict[str, Any]] = {}
    issues: list[str] = []
    for path in sorted(records_root.glob("*/*.yaml")):
        record = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict) or not isinstance(record.get("pid"), str):
            issues.append(f"{path}: record has no string pid")
            continue
        pid = record["pid"]
        if pid in records:
            issues.append(f"duplicate pid: {pid}")
            continue
        record["_class"] = path.parent.name
        record["_path"] = str(path)
        records[pid] = record
    return records, issues


def is_candidate_pid(value: str) -> bool:
    return value.startswith(("ror:", "xyzrins:", "https://doi.org/"))


def edge_matches(
    edge: tuple[str, str, str, str, str],
    shape: tuple[str, str, str],
) -> bool:
    return edge[0] == shape[0] and edge[2] == shape[1] and edge[3] == shape[2]


def reverse_of(edge: tuple[str, str, str, str, str]) -> tuple[str, str]:
    return edge[4], edge[1]


def check(records_root: Path) -> dict[str, Any]:
    records, issues = load_records(records_root)
    classes = {str(record["_class"]) for record in records.values()}
    missing_classes = sorted(REQUIRED_CLASSES - classes)
    if missing_classes:
        issues.append(f"missing required classes: {', '.join(missing_classes)}")

    edges: list[tuple[str, str, str, str, str]] = []
    graph: dict[str, set[str]] = defaultdict(set)
    for source_pid, record in records.items():
        source_class = str(record["_class"])
        for attribute in record.get("attributes", []):
            if not isinstance(attribute, dict):
                continue
            predicate = attribute.get("predicate")
            target_pid = attribute.get("value")
            if not isinstance(predicate, str) or not isinstance(target_pid, str):
                continue
            if predicate not in EXPECTED_TARGET_CLASSES:
                if is_candidate_pid(target_pid) and target_pid not in records:
                    issues.append(
                        f"{source_pid} {predicate}: missing target {target_pid}"
                    )
                continue
            target = records.get(target_pid)
            if target is None:
                issues.append(f"{source_pid} {predicate}: missing target {target_pid}")
                continue
            target_class = str(target["_class"])
            if target_class not in EXPECTED_TARGET_CLASSES[predicate]:
                expected = ", ".join(sorted(EXPECTED_TARGET_CLASSES[predicate]))
                issues.append(
                    f"{source_pid} {predicate}: {target_pid} is {target_class}, "
                    f"expected {expected}"
                )
                continue
            edge = (source_class, source_pid, predicate, target_class, target_pid)
            edges.append(edge)
            graph[source_pid].add(target_pid)
            graph[target_pid].add(source_pid)

    for left, right in REQUIRED_RECIPROCALS:
        left_edges = [edge for edge in edges if edge_matches(edge, left)]
        right_edges = [edge for edge in edges if edge_matches(edge, right)]
        if not left_edges:
            issues.append(f"missing required relationship shape: {left}")
        if not right_edges:
            issues.append(f"missing required relationship shape: {right}")
        right_pairs = {reverse_of(edge) for edge in right_edges}
        left_pairs = {(edge[1], edge[4]) for edge in left_edges}
        for edge in left_edges:
            if (edge[1], edge[4]) not in right_pairs:
                issues.append(
                    f"missing reciprocal for {edge[1]} {edge[2]} {edge[4]}"
                )
        for edge in right_edges:
            if reverse_of(edge) not in left_pairs:
                issues.append(
                    f"missing reciprocal for {edge[1]} {edge[2]} {edge[4]}"
                )

    if records:
        start = next(iter(records))
        seen = {start}
        pending = deque([start])
        while pending:
            source = pending.popleft()
            for target in graph[source] - seen:
                seen.add(target)
                pending.append(target)
        disconnected = sorted(set(records) - seen)
        if disconnected:
            issues.append(f"disconnected records: {', '.join(disconnected)}")
    else:
        seen = set()

    publications = [
        record
        for record in records.values()
        if record["_class"] == "XYZPublication"
    ]
    for publication in publications:
        pid = str(publication["pid"])
        if not pid.startswith("https://doi.org/") or not DOI.fullmatch(
            pid.removeprefix("https://doi.org/")
        ):
            issues.append(f"publication pid is not a valid DOI URL: {pid}")
        notations = [
            str(identifier.get("notation"))
            for identifier in publication.get("identifiers", [])
            if isinstance(identifier, dict) and identifier.get("notation")
        ]
        if not any(DOI.fullmatch(notation) for notation in notations):
            issues.append(f"{pid}: no valid DOI notation")
        if not any(ISSN.fullmatch(notation) for notation in notations):
            issues.append(f"{pid}: no valid ISSN notation")

    return {
        "connected_record_count": len(seen),
        "issues": sorted(set(issues)),
        "record_count": len(records),
        "relationship_count": len(edges),
        "status": "valid" if not issues else "invalid",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records_root", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = check(args.records_root)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return int(bool(report["issues"]))


if __name__ == "__main__":
    raise SystemExit(main())
