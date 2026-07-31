#!/usr/bin/env python3
"""Prove that a dangling candidate PID stops publication."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

import yaml


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records-root", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True)
    args = parser.parse_args()

    invalid_root = args.build_dir / "invalid-relationships"
    shutil.copytree(args.records_root, invalid_root)
    project_path = invalid_root / "XYZProject" / "datalad.yaml"
    project = yaml.safe_load(project_path.read_text(encoding="utf-8"))
    lead = next(
        attribute
        for attribute in project["attributes"]
        if attribute.get("predicate") == "dcterms:contributor"
    )
    lead["value"] = "xyzrins:persons/missing-milestone-person"
    project_path.write_text(
        yaml.safe_dump(project, sort_keys=False), encoding="utf-8"
    )

    checker = Path(__file__).with_name("check_relationships.py")
    process = subprocess.run(
        [sys.executable, str(checker), str(invalid_root)],
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode == 0 or "missing target" not in process.stdout:
        print(process.stdout)
        print(process.stderr, file=sys.stderr)
        raise SystemExit("Dangling relationship was not rejected")
    print("Invalid-relationship publication gate: rejected as expected")


if __name__ == "__main__":
    main()
