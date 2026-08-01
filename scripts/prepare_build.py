#!/usr/bin/env python3
"""Create an isolated Dump Things store and Hugo content workspace."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil

import yaml

from project_records import CLASS_SECTIONS


def safe_reset(build_dir: Path, repository: Path) -> None:
    resolved = build_dir.resolve()
    if resolved.parent != repository or not resolved.name.startswith("build"):
        raise ValueError(
            f"Refusing to replace non-build path outside repository: {resolved}"
        )
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir()


def copy_metadata(metadata_root: Path, store: Path) -> tuple[Path, list[str]]:
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
    classes = sorted(
        path.name
        for path in (metadata_root / "records").iterdir()
        if path.is_dir() and not path.name.startswith(".")
    )
    if not classes:
        raise ValueError(f"No record class directories below {metadata_root / 'records'}")
    return schema, classes


def write_validation_streams(
    records_root: Path,
    output: Path,
    classes: list[str],
    manifest_path: Path,
) -> None:
    """Serialize every copied canonical record for upstream validation.

    Reading the isolated store copy, rather than the source tree a second
    time, guarantees that validation and publication operate on the same
    bytes.  Recursive discovery also prevents a nested record from silently
    bypassing the validation gate.
    """
    output.mkdir(parents=True)
    manifest_records: list[dict[str, str]] = []
    discovered: set[Path] = set()
    for class_name in classes:
        records = []
        class_root = records_root / class_name
        for path in sorted(
            candidate
            for candidate in class_root.rglob("*.yaml")
            if candidate.is_file()
        ):
            discovered.add(path.resolve())
            record = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(record, dict) or not record.get("pid"):
                raise ValueError(f"Record must be a mapping with a PID: {path}")
            records.append(json.dumps(record, ensure_ascii=False, sort_keys=True))
            manifest_records.append(
                {
                    "class_name": class_name,
                    "pid": str(record["pid"]),
                    "relative_path": path.relative_to(records_root).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
        if not records:
            raise ValueError(f"No YAML records for class {class_name}")
        (output / f"{class_name}.jsonl").write_text(
            "\n".join(records) + "\n", encoding="utf-8"
        )

    canonical_yaml = {
        path.resolve()
        for path in records_root.rglob("*.yaml")
        if path.is_file() and path.name != ".dumpthings.yaml"
    }
    if discovered != canonical_yaml:
        omitted = sorted(str(path) for path in canonical_yaml - discovered)
        raise ValueError(f"Canonical YAML records were not assigned to a class: {omitted}")

    manifest = {"records": sorted(manifest_records, key=lambda item: item["relative_path"])}
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_store_config(store: Path, schema: Path, classes: list[str]) -> Path:
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
                "use_classes": classes,
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
    """Copy editorial pages and entity resources without entity page overrides.

    Entity facts and page bodies are owned by validated metadata.  A section's
    top-level ``_index.md`` may describe the collection, and nested non-Markdown
    files may supply page-bundle resources such as depictions.  A nested
    Markdown entity page would otherwise be able to publish without a record,
    so reject it instead of silently copying or ignoring it.
    """
    source = repository / "content"
    entity_sections = set(CLASS_SECTIONS.values())
    output.mkdir()
    for entry in sorted(source.iterdir()):
        if entry.name in {"CNAME", "pages"}:
            continue
        destination = output / entry.name
        if not entry.is_dir() or entry.name not in entity_sections:
            if entry.is_dir():
                shutil.copytree(entry, destination)
            else:
                shutil.copy2(entry, destination, follow_symlinks=True)
            continue

        destination.mkdir()
        for path in sorted(entry.rglob("*")):
            relative = path.relative_to(entry)
            target = destination / relative
            if path.is_dir() and not path.is_symlink():
                target.mkdir(exist_ok=True)
                continue
            if path.suffix.lower() in {".md", ".markdown"} and relative != Path(
                "_index.md"
            ):
                raise ValueError(
                    "Entity Markdown must be generated from validated metadata: "
                    f"{path.relative_to(repository)}"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target, follow_symlinks=True)


def copy_static_files(repository: Path, output: Path) -> None:
    shutil.copytree(repository / "static", output)


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
    schema, classes = copy_metadata(metadata_root, store)
    config = write_store_config(store, schema, classes)
    write_validation_streams(
        store / "curated",
        build_dir / "validation-jsonl",
        classes,
        build_dir / "source-manifest.json",
    )

    content = build_dir / "hugo" / "content"
    content.parent.mkdir()
    copy_editorial_content(repository, content)
    copy_static_files(repository, build_dir / "hugo" / "static")

    print(config)


if __name__ == "__main__":
    main()
