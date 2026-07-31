#!/usr/bin/env python3
"""Check required preview pages and write a deterministic site manifest."""

from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse


REQUIRED = {
    "index.html": ["Center for Open Neuroscience", "ror:04tfhh831", "DataLad"],
    "persons/yaroslav-halchenko/index.html": [
        "Yaroslav O. Halchenko",
        "xyzrins:persons/yaroslav-halchenko",
        "Connected projects",
        "DataLad",
    ],
    "projects/datalad/index.html": [
        "DataLad",
        "xyzrins:projects/datalad",
        "Related publication",
        "Software output",
        "Center for Open Neuroscience",
        "Yaroslav O. Halchenko",
    ],
    "publications/datalad-joss-2021/index.html": [
        "10.21105/joss.03262",
        "Selected author",
        "Yaroslav O. Halchenko",
    ],
    "instruments/datalad/index.html": [
        "DataLad software",
        "xyzrins:instruments/datalad",
        "Connected project",
        "DataLad",
    ],
}

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
    "img/con-logo.png",
    "img/con-logo.svg",
    "img/datalad-logo.png",
    "img/yaroslav-halchenko.jpg",
    "site.webmanifest",
]


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
            elif name in {"href", "src"}:
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", type=Path)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    for relative, needles in REQUIRED.items():
        path = args.site / relative
        if not path.is_file():
            raise SystemExit(f"Missing required preview page: {relative}")
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                raise SystemExit(f"{relative} does not contain {needle!r}")
    for relative in REQUIRED_COMPATIBILITY_PATHS + REQUIRED_ASSETS:
        if not (args.site / relative).is_file():
            raise SystemExit(f"Missing required preview path: {relative}")
    anchor_checks = {
        "projects/index.html": "id=datalad_",
        "whoweare/index.html": "id=yaroslav_o_halchenko_",
    }
    for relative, needle in anchor_checks.items():
        text = (args.site / relative).read_text(encoding="utf-8")
        if needle not in text:
            raise SystemExit(f"{relative} does not retain {needle!r}")
    if (args.site / "CNAME").exists():
        raise SystemExit("Preview must not publish the production CNAME")
    checked_links = check_internal_links(args.site, args.base_url)
    checked_manifest_icons = check_web_manifest(args.site)

    entries = [
        f"{digest(path)}  {path.relative_to(args.site).as_posix()}"
        for path in sorted(args.site.rglob("*"))
        if path.is_file() and path.name != ".DS_Store"
    ]
    args.manifest.write_text("\n".join(entries) + "\n", encoding="utf-8")
    print(
        f"Verified {len(REQUIRED)} metadata pages, "
        f"{len(REQUIRED_COMPATIBILITY_PATHS)} compatibility paths, "
        f"{len(REQUIRED_ASSETS)} assets, and {len(entries)} site files"
        f"; checked {checked_links} internal links and "
        f"{checked_manifest_icons} manifest icons"
    )


if __name__ == "__main__":
    main()
