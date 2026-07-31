#!/usr/bin/env python3
"""Create an isolated Dump Things store and Hugo content workspace."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import yaml


CLASSES = [
    "XYZInstrument",
    "XYZOrganization",
    "XYZPerson",
    "XYZProject",
    "XYZPublication",
]


def safe_reset(build_dir: Path, repository: Path) -> None:
    resolved = build_dir.resolve()
    if resolved.parent != repository or not resolved.name.startswith("build"):
        raise ValueError(
            f"Refusing to replace non-build path outside repository: {resolved}"
        )
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir()


def copy_metadata(metadata_root: Path, store: Path) -> Path:
    curated = store / "curated"
    shutil.copytree(
        metadata_root / "records",
        curated,
        ignore=shutil.ignore_patterns(".directory_dir_index.db"),
    )
    shutil.copytree(metadata_root / "schema", store / "schema")
    (store / "incoming").mkdir()
    schema = (store / "schema" / "demo-research-information.static.yaml").resolve()
    record_config_path = curated / ".dumpthings.yaml"
    record_config = yaml.safe_load(record_config_path.read_text(encoding="utf-8"))
    record_config["schema"] = str(schema)
    record_config_path.write_text(
        yaml.safe_dump(record_config, sort_keys=False), encoding="utf-8"
    )
    return schema


def write_store_config(store: Path, schema: Path) -> Path:
    config = {
        "type": "collections",
        "version": 2,
        "pid": "dump_things:config",
        "collections": {
            "research_info": {
                "default_token": "preview-reader",
                "schema": str(schema),
                "curated": "curated",
                "incoming": "incoming",
                "backend": {
                    "type": "record_dir+stl",
                    "mapping_method": "after-last-colon",
                },
                "auth_sources": [{"type": "config"}],
                "use_classes": CLASSES,
            }
        },
        "tokens": {
            "preview-reader": {
                "user_id": "preview-reader",
                "representation": "preview-reader",
                "collections": {
                    "research_info": {
                        "mode": "READ_CURATED",
                        "incoming_label": "",
                    }
                },
            },
            "preview-validator": {
                "user_id": "preview-validator",
                "representation": "preview-validator",
                "collections": {
                    "research_info": {
                        "mode": "WRITE_COLLECTION",
                        "incoming_label": "validation",
                    }
                },
            },
        },
        "admin_tokens": {},
    }
    path = store / "config.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return path


def copy_editorial_content(repository: Path, output: Path) -> None:
    source = repository / "content"
    shutil.copytree(
        source,
        output,
        ignore=shutil.ignore_patterns("CNAME", "pages"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata-root", type=Path, default=Path("metadata"))
    parser.add_argument("--build-dir", type=Path, default=Path("build"))
    args = parser.parse_args()

    repository = Path(__file__).resolve().parents[1]
    build_dir = (
        args.build_dir
        if args.build_dir.is_absolute()
        else repository / args.build_dir
    )
    metadata_root = (
        args.metadata_root
        if args.metadata_root.is_absolute()
        else repository / args.metadata_root
    ).resolve()

    safe_reset(build_dir, repository)
    store = build_dir / "store"
    store.mkdir()
    schema = copy_metadata(metadata_root, store)
    config = write_store_config(store, schema)

    content = build_dir / "hugo" / "content"
    content.parent.mkdir()
    copy_editorial_content(repository, content)

    print(config)


if __name__ == "__main__":
    main()
