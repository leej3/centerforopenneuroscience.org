#!/usr/bin/env python3
"""Check the generic metadata site contract and write a deterministic manifest."""

from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlparse


REQUIRED_COMPATIBILITY_PATHS = [
    "engage.html",
    "engage/index.html",
    "projects.html",
    "projects/index.html",
    "support.html",
    "support/index.html",
    "whoweare.html",
    "whoweare/index.html",
]

REQUIRED_ASSETS = [
    "favicon.svg",
    "filter-list.css",
    "filter-list.js",
    "graph.css",
    "graph.js",
    "graph.json",
    "grid-list.css",
    "img/con-logo.png",
    "site.webmanifest",
]

REQUIRED_DEPICTION_PATHS = {
    "instruments/datalad",
    "persons/yaroslav-halchenko",
    "projects/datalad",
}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.references: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        del tag
        for name, value in attrs:
            if not value:
                continue
            if name in {"id", "name"}:
                self.ids.add(value)
            elif name in {"href", "src", "data-graph-url", "data-site-root"}:
                self.references.append(value)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_page(path: Path) -> PageParser:
    parser = PageParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def page_url(relative: Path) -> str:
    value = relative.as_posix()
    if relative.name == "index.html":
        parent = relative.parent.as_posix()
        return "" if parent == "." else parent.rstrip("/") + "/"
    return value


def check_internal_links(site: Path, base_url: str) -> int:
    base_url = base_url.rstrip("/") + "/"
    parsed_base = urlparse(base_url)
    base_path = parsed_base.path.rstrip("/") + "/"
    parsed_pages: dict[Path, PageParser] = {}
    checked = 0
    for source in sorted(site.rglob("*.html")):
        relative = source.relative_to(site)
        source_parser = parsed_pages.setdefault(source, parse_page(source))
        source_url = urljoin(base_url, page_url(relative))
        for reference in source_parser.references:
            if reference.startswith(("data:", "javascript:", "mailto:", "tel:")):
                continue
            target_url = urljoin(source_url, reference)
            parsed_target = urlparse(target_url)
            if parsed_target.scheme not in {"http", "https"}:
                continue
            if parsed_target.netloc != parsed_base.netloc:
                continue
            target_path = unquote(parsed_target.path)
            if not target_path.startswith(base_path):
                raise SystemExit(
                    f"{relative}: internal reference escapes Pages base path: "
                    f"{reference}"
                )
            target_relative = target_path[len(base_path) :]
            if not target_relative or target_relative.endswith("/"):
                target_relative += "index.html"
            target = site / target_relative
            if not target.is_file():
                raise SystemExit(f"{relative}: missing internal target {reference}")
            if parsed_target.fragment and target.suffix == ".html":
                target_parser = parsed_pages.setdefault(target, parse_page(target))
                if parsed_target.fragment not in target_parser.ids:
                    raise SystemExit(
                        f"{relative}: missing fragment target {reference}"
                    )
            checked += 1
    return checked


def check_web_manifest(site: Path) -> int:
    manifest = json.loads((site / "site.webmanifest").read_text(encoding="utf-8"))
    if manifest.get("name") != "Center for Open Neuroscience":
        raise SystemExit("Web manifest does not identify CON")
    icons = manifest.get("icons")
    if not isinstance(icons, list) or not icons:
        raise SystemExit("Web manifest has no icons")
    for icon in icons:
        source = icon.get("src") if isinstance(icon, dict) else None
        if not isinstance(source, str) or source.startswith("/"):
            raise SystemExit(f"Web manifest icon is not base-path relative: {source!r}")
        if not (site / source).is_file():
            raise SystemExit(f"Web manifest icon is missing: {source}")
    return len(icons)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not records:
        raise SystemExit("Projection contains no records")
    return records


def record_page(site: Path, record: dict[str, Any]) -> Path:
    route = str(record["site_path"])
    return site / route / "index.html" if route else site / "index.html"


def check_metadata_pages(
    site: Path, records: list[dict[str, Any]], graph: dict[str, Any]
) -> tuple[int, int]:
    by_pid = {str(record["pid"]): record for record in records}
    page_text: dict[str, str] = {}
    for pid, record in by_pid.items():
        path = record_page(site, record)
        if not path.is_file():
            raise SystemExit(f"Missing projected page for {pid}: {path.relative_to(site)}")
        text = path.read_text(encoding="utf-8")
        page_text[pid] = text
        for value in (
            record["page_title"],
            pid,
            "metadata-graph",
            "data-graph-links",
        ):
            if str(value) not in text:
                raise SystemExit(
                    f"{path.relative_to(site)} does not contain {value!r}"
                )
        route = str(record["site_path"])
        if route:
            index = site / str(record["class_section"]) / "index.html"
            if not index.is_file() or str(record["page_title"]) not in index.read_text(
                encoding="utf-8"
            ):
                raise SystemExit(f"Class index does not list {pid}")
        if route in REQUIRED_DEPICTION_PATHS and "metadata-term-depiction" not in text:
            raise SystemExit(f"Projected term has no bundle depiction: {route}")

    expected_pages = {
        Path(str(record["site_path"])) / "index.html"
        for record in records
        if record["site_path"]
    }
    for section in {str(record["class_section"]) for record in records}:
        section_root = site / section
        if not section_root.is_dir():
            continue
        for path in section_root.rglob("index.html"):
            relative = path.relative_to(site)
            if relative == Path(section) / "index.html":
                continue
            if relative not in expected_pages:
                raise SystemExit(
                    "Entity page is not backed by projected metadata: "
                    f"{relative.as_posix()}"
                )

    graph_nodes = graph.get("nodes")
    graph_edges = graph.get("edges")
    if not isinstance(graph_nodes, list) or not isinstance(graph_edges, list):
        raise SystemExit("graph.json does not contain node and edge lists")
    node_pids = {str(node.get("id")) for node in graph_nodes}
    if node_pids != set(by_pid):
        raise SystemExit("graph.json nodes do not match projected records")
    for node in graph_nodes:
        if node.get("url") != by_pid[str(node["id"])]["page_url"]:
            raise SystemExit(f"Graph node URL disagrees with projection: {node['id']}")
    for edge in graph_edges:
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        if source not in by_pid or target not in by_pid or not edge.get("type"):
            raise SystemExit(f"Invalid graph edge: {edge}")
        if edge.get("type") == "related_to" and edge.get("symmetric") is not True:
            raise SystemExit(f"Symmetric graph edge lost its semantics: {edge}")
        if str(by_pid[target]["page_title"]) not in page_text[source]:
            raise SystemExit(f"Source page does not navigate to related record: {source}")
        if str(by_pid[source]["page_title"]) not in page_text[target]:
            raise SystemExit(f"Target page has no reverse navigation: {target}")
    return len(by_pid), len(graph_edges)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", type=Path)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--projected-records", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    for relative in REQUIRED_COMPATIBILITY_PATHS + REQUIRED_ASSETS:
        if not (args.site / relative).is_file():
            raise SystemExit(f"Missing required preview path: {relative}")
    if (args.site / "CNAME").exists():
        raise SystemExit("Preview must not publish the production CNAME")

    records = load_jsonl(args.projected_records)
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    record_count, edge_count = check_metadata_pages(args.site, records, graph)
    checked_links = check_internal_links(args.site, args.base_url)
    checked_manifest_icons = check_web_manifest(args.site)

    entries = [
        f"{digest(path)}  {path.relative_to(args.site).as_posix()}"
        for path in sorted(args.site.rglob("*"))
        if path.is_file() and path.name != ".DS_Store"
    ]
    args.manifest.write_text("\n".join(entries) + "\n", encoding="utf-8")
    print(
        f"Verified {record_count} metadata pages, {edge_count} graph edges, "
        f"{len(REQUIRED_COMPATIBILITY_PATHS)} compatibility paths, "
        f"{len(REQUIRED_ASSETS)} functional assets, and {len(entries)} site files; "
        f"checked {checked_links} internal links and "
        f"{checked_manifest_icons} manifest icons"
    )


if __name__ == "__main__":
    main()
