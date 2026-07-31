#!/usr/bin/env python3
"""Prove that the publication validator rejects an invalid record."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=Path("build"))
    parser.add_argument("--service-url", default="http://127.0.0.1:8111")
    args = parser.parse_args()

    invalid_root = args.build_dir / "invalid-records" / "XYZProject"
    invalid_root.mkdir(parents=True)
    (invalid_root / "invalid.yaml").write_text(
        "pid: xyzrins:projects/invalid\nunknown_milestone_field: true\n",
        encoding="utf-8",
    )
    validator = Path(__file__).with_name("validate_records.py")
    process = subprocess.run(
        [
            sys.executable,
            str(validator),
            str(args.build_dir / "invalid-records"),
            "--service-url",
            args.service_url,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode == 0 or '"invalid_count": 1' not in process.stdout:
        print(process.stdout)
        print(process.stderr, file=sys.stderr)
        raise SystemExit("Invalid record was not rejected by the publication gate")
    print("Invalid-record publication gate: rejected as expected")


if __name__ == "__main__":
    main()
