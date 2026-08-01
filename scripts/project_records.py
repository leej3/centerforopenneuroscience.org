#!/usr/bin/env python3
"""Project validated records into generic site links, routes, and graph data.

This is the single temporary compatibility boundary for Milestone 1.  The
pinned schema cannot yet carry the native qualified relationship records, so
the canonical records preserve a small set of relationships as
AttributeSpecification values.  This script normalizes those predicates
without knowing any CON record PID, label, route, or asset.

Delete the relationship-normalization portion once the native schema records
round-trip through Dump Things and qri.  Generic class routing and graph output
can remain useful independently.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

import yaml


CLASS_SECTIONS = {
    "xyzri:XYZDataset": "datasets",
    "xyzri:XYZInstrument": "instruments",
    "xyzri:XYZObjective": "objectives",
    "xyzri:XYZOrganization": "organizations",
    "xyzri:XYZPerson": "persons",
    "xyzri:XYZProject": "projects",
    "xyzri:XYZPublication": "publications",
    "xyzri:XYZTopic": "topics",
}

RELATION_LABELS = {
    "about": "About",
    "associated_with": "Associated with",
    "attributed_to": "Attributed to",
    "related_to": "Related to",
}

# The predicates temporarily encoded as AttributeSpecification values while
# native relationship records do not round-trip through the pinned schema.
# Every one of these predicates denotes an edge within this publication pool.
COMPATIBILITY_RELATION_PREDICATES = frozenset(
    {
        "dcterms:contributor",
        "dcterms:creator",
        "dcterms:relation",
        "schema:about",
        "schema:member",
        "schema:memberOf",
        "schema:subjectOf",
    }
)


def slugify(value: str) -> str:
    """Return a stable path component without interpreting record identity."""
    value = unquote(value).strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    return value.strip("-.") or "record"


def route_for(record: dict[str, Any], root_pid: str) -> tuple[str, str, str | None]:
    """Return the site path, term slug, and taxonomy for a record."""
    pid = str(record["pid"])
    schema_type = str(record.get("schema_type", ""))
    try:
        section = CLASS_SECTIONS[schema_type]
    except KeyError as error:
        raise ValueError(f"No site section for schema type {schema_type!r}") from error

    section_prefix = f"xyzrins:{section}/"
    if pid.startswith(section_prefix):
        slug = "/".join(
            slugify(part) for part in pid.removeprefix(section_prefix).split("/")
        )
    elif pid.startswith(("https://doi.org/", "http://doi.org/")):
        doi = urlparse(pid).path.lstrip("/").replace("/", "-")
        slug = f"doi-{slugify(doi)}"
    elif ":" in pid and not pid.startswith(("http://", "https://")):
        prefix, reference = pid.split(":", 1)
        slug = f"{slugify(prefix)}-{slugify(reference)}"
    else:
        parsed = urlparse(pid)
        route_source = f"{parsed.netloc}-{parsed.path}" if parsed.netloc else pid
        slug = slugify(route_source)

    if pid == root_pid:
        return "", slug, None
    return f"{section}/{slug}", slug, section


def title_for(record: dict[str, Any]) -> str:
    for field in ("display_label", "formatted_name", "title", "name", "short_name"):
        if record.get(field):
            return str(record[field])
    return str(record["pid"])


def issued_date(record: dict[str, Any]) -> str | None:
    for attribute in record.get("attributes", []):
        if attribute.get("predicate") == "dcterms:issued" and attribute.get("value"):
            return str(attribute["value"])
    return None


def external_links(record: dict[str, Any], known_pids: set[str]) -> list[dict[str, str]]:
    labels = {
        "foaf:homepage": "Homepage",
        "obo:APOLLO_SV_00000488": "Source code",
        "obo:NGBO_6000416": "Documentation",
    }
    links: list[dict[str, str]] = []
    for attribute in record.get("attributes", []):
        predicate = attribute.get("predicate")
        value = attribute.get("value")
        if (
            predicate in labels
            and isinstance(value, str)
            and value not in known_pids
            and value.startswith(("http://", "https://"))
        ):
            links.append({"label": labels[predicate], "url": value})
    return sorted(links, key=lambda item: (item["label"], item["url"]))


def normalized_edge(source: str, target: str, predicate: str) -> dict[str, Any]:
    """Normalize one compatibility assertion and retain the raw assertion."""
    assertion = {"source": source, "predicate": predicate, "target": target}
    if predicate == "dcterms:creator":
        return {
            "source": source,
            "target": target,
            "relation": "attributed_to",
            "assertions": [assertion],
        }
    if predicate == "schema:about":
        return {
            "source": source,
            "target": target,
            "relation": "about",
            "assertions": [assertion],
        }
    if predicate == "schema:subjectOf":
        return {
            "source": target,
            "target": source,
            "relation": "about",
            "assertions": [assertion],
        }
    if predicate in {"dcterms:contributor", "schema:member"}:
        return {
            "source": source,
            "target": target,
            "relation": "associated_with",
            "assertions": [assertion],
        }
    if predicate == "schema:memberOf":
        return {
            "source": target,
            "target": source,
            "relation": "associated_with",
            "assertions": [assertion],
        }
    if predicate == "dcterms:relation":
        left, right = sorted((source, target))
        return {
            "source": left,
            "target": right,
            "relation": "related_to",
            "symmetric": True,
            "assertions": [assertion],
        }
    return {
        "source": source,
        "target": target,
        "relation": predicate,
        "assertions": [assertion],
    }


def compatible_edges(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    by_pid = {str(record["pid"]): record for record in records}
    raw_edges: list[dict[str, Any]] = []
    for record in records:
        source = str(record["pid"])
        for attribute in record.get("attributes", []):
            target = attribute.get("value")
            predicate = attribute.get("predicate")
            if predicate not in COMPATIBILITY_RELATION_PREDICATES:
                continue
            if not isinstance(target, str) or target not in by_pid:
                raise ValueError(
                    f"{source}: compatibility relationship target is absent: {target} "
                    f"(predicate {predicate})"
                )
            raw_edges.append(normalized_edge(source, target, predicate))

    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    for edge in raw_edges:
        key = (edge["source"], edge["target"], edge["relation"])
        if key in merged:
            merged[key]["assertions"].extend(edge["assertions"])
        else:
            merged[key] = edge

    specific_by_pair: dict[frozenset[str], list[dict[str, Any]]] = defaultdict(list)
    generic_edges: list[dict[str, Any]] = []
    for edge in merged.values():
        if edge["relation"] == "related_to":
            generic_edges.append(edge)
        else:
            specific_by_pair[frozenset((edge["source"], edge["target"]))].append(edge)

    edges = [edge for group in specific_by_pair.values() for edge in group]
    for generic in generic_edges:
        pair = frozenset((generic["source"], generic["target"]))
        candidates = specific_by_pair.get(pair)
        if not candidates:
            edges.append(generic)
            continue
        # The more informative relation survives, but the exact generic
        # assertion remains attached for a lossless compatibility boundary.
        survivor = min(
            candidates,
            key=lambda edge: (edge["source"], edge["target"], edge["relation"]),
        )
        survivor["assertions"].extend(generic["assertions"])
    for edge in edges:
        edge["assertions"] = sorted(
            edge["assertions"],
            key=lambda item: (item["source"], item["predicate"], item["target"]),
        )
        edge_key = "\0".join((edge["source"], edge["relation"], edge["target"]))
        edge["id"] = f"edge-{hashlib.sha256(edge_key.encode()).hexdigest()[:12]}"
    return sorted(
        edges, key=lambda edge: (edge["source"], edge["target"], edge["relation"])
    ), len(raw_edges)


def link_for(edge: dict[str, Any], object_pid: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "object": object_pid,
        "predicate": edge["relation"],
        "relation_label": RELATION_LABELS.get(
            edge["relation"], edge["relation"].replace("_", " ").title()
        ),
        "assertions": edge["assertions"],
    }
    if edge.get("symmetric"):
        result["symmetric"] = True
    return result


def project(
    records: list[dict[str, Any]], root_pid: str, content_root: Path, base_url: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    by_pid = {str(record["pid"]): record for record in records}
    if len(by_pid) != len(records):
        raise ValueError("Record PIDs must be unique")
    if root_pid not in by_pid:
        raise ValueError(f"Configured root PID is absent: {root_pid}")

    base_url = base_url.rstrip("/") + "/"
    routes: dict[str, str] = {}
    route_values: list[tuple[dict[str, Any], str, str, str | None]] = []
    for record in records:
        route, slug, taxonomy = route_for(record, root_pid)
        pid = str(record["pid"])
        if route in routes:
            raise ValueError(
                f"Site route collision at {route or '/'}: {routes[route]} and {pid}"
            )
        routes[route] = pid
        route_values.append((record, route, slug, taxonomy))

    for record, route, slug, taxonomy in route_values:
        record["site_path"] = route
        record["output_path"] = str(content_root / route / "_index.md")
        record["term_slug"] = slug
        record["class_section"] = CLASS_SECTIONS[str(record["schema_type"])]
        record["record_taxonomy"] = taxonomy
        record["page_title"] = title_for(record)
        record["page_url"] = urljoin(base_url, f"{route}/" if route else "")
        record["page_ref"] = urlparse(record["page_url"]).path
        record["date"] = issued_date(record)
        record["external_links"] = external_links(record, set(by_pid))

    edges, raw_edge_count = compatible_edges(records)
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)
    forward_targets: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        outgoing[source].append(link_for(edge, target))
        incoming[target].append(link_for(edge, source))
        forward_targets[source].add(target)
        if edge.get("symmetric"):
            outgoing[target].append(link_for(edge, source))
            incoming[source].append(link_for(edge, target))
            forward_targets[target].add(source)

    for record in records:
        pid = str(record["pid"])
        record["links_out"] = sorted(
            outgoing[pid], key=lambda link: (link["predicate"], link["object"])
        )
        record["links_in"] = sorted(
            incoming[pid], key=lambda link: (link["predicate"], link["object"])
        )
        taxonomies: dict[str, list[str]] = defaultdict(list)
        for target_pid in sorted(forward_targets[pid]):
            target = by_pid[target_pid]
            taxonomy = target["record_taxonomy"]
            term = target["term_slug"]
            if taxonomy and term not in taxonomies[taxonomy]:
                taxonomies[taxonomy].append(term)
        record["taxonomies"] = {
            name: sorted(terms) for name, terms in sorted(taxonomies.items())
        }

    return sorted(records, key=lambda record: str(record["pid"])), edges, raw_edge_count


def graph_data(
    records: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> dict[str, Any]:
    degrees: dict[str, int] = defaultdict(int)
    graph_edges: list[dict[str, Any]] = []
    for edge in edges:
        degrees[edge["source"]] += 1
        degrees[edge["target"]] += 1
        graph_edge: dict[str, Any] = {
            "id": edge["id"],
            "source": edge["source"],
            "target": edge["target"],
            "type": edge["relation"],
        }
        if edge.get("symmetric"):
            graph_edge["symmetric"] = True
        graph_edges.append(graph_edge)
    nodes = [
        {
            "id": record["pid"],
            "label": record["page_title"],
            "type": record["class_section"].removesuffix("s"),
            "size": 1 + degrees[str(record["pid"])],
            "url": record["page_url"],
        }
        for record in records
    ]
    return {"nodes": nodes, "edges": graph_edges}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def reconcile_source_manifest(records: list[dict[str, Any]], manifest_path: Path) -> None:
    """Require the upstream export to match canonical source PID/class pairs."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest.get("records")
    if not isinstance(entries, list):
        raise ValueError(f"Invalid source manifest records list: {manifest_path}")

    expected_items = [
        (str(entry["pid"]), str(entry["class_name"])) for entry in entries
    ]
    actual_items = [
        (str(record["pid"]), str(record.get("schema_type", "")).rsplit(":", 1)[-1])
        for record in records
    ]
    if len(set(expected_items)) != len(expected_items):
        raise ValueError("Source manifest contains duplicate PID/class pairs")
    if len(set(actual_items)) != len(actual_items):
        raise ValueError("Upstream export contains duplicate PID/class pairs")

    expected = set(expected_items)
    actual = set(actual_items)
    if expected != actual:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise ValueError(
            "Upstream export does not match the canonical source manifest; "
            f"missing={missing}, unexpected={unexpected}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-config", type=Path, default=Path("metadata/site.yaml"))
    parser.add_argument("--content-root", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    args = parser.parse_args()

    config = yaml.safe_load(args.site_config.read_text(encoding="utf-8"))
    root_pid = str(config["root_pid"])
    records = [json.loads(line) for line in sys.stdin if line.strip()]
    reconcile_source_manifest(records, args.source_manifest)
    projected, edges, raw_edge_count = project(
        records, root_pid, args.content_root, args.base_url
    )
    write_json(args.graph, graph_data(projected, edges))
    report = {
        "canonical_edge_count": len(edges),
        "record_count": len(projected),
        "raw_internal_assertion_count": raw_edge_count,
        "root_pid": root_pid,
    }
    write_json(args.report, report)
    for record in projected:
        print(json.dumps(record, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
