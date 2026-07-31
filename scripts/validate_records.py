#!/usr/bin/env python3
"""Validate every individual YAML record through Dump Things."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import yaml


def jobs(records_root: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path in sorted(records_root.glob("*/*.yaml")):
        record = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict) or not record.get("pid"):
            raise ValueError(f"Record must be a mapping with a pid: {path}")
        result.append(
            {
                "class": path.parent.name,
                "file": str(path),
                "pid": record["pid"],
                "record": record,
            }
        )
    if not result:
        raise ValueError(f"No individual YAML records found below {records_root}")
    return result


def validate(
    job: dict[str, Any], service_url: str, collection: str, token: str
) -> dict[str, Any]:
    request = Request(
        f"{service_url.rstrip('/')}/{collection}/validate/record/{job['class']}",
        data=json.dumps(job["record"]).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-DumpThings-Token": token,
        },
    )
    result = {key: job[key] for key in ("class", "file", "pid")}
    try:
        with urlopen(request, timeout=60) as response:
            response.read()
            result["status"] = response.status
    except HTTPError as error:
        raw = error.read().decode(errors="replace")
        try:
            result["detail"] = json.loads(raw)
        except json.JSONDecodeError:
            result["detail"] = raw
        result["status"] = error.code
    return result


def run(args: argparse.Namespace) -> int:
    results = [
        validate(job, args.service_url, args.collection, args.token)
        for job in jobs(args.records_root)
    ]
    failures = [
        result for result in results if not 200 <= int(result["status"]) < 300
    ]
    status_counts = Counter(str(result["status"]) for result in results)
    report = {
        "collection": args.collection,
        "failures": failures,
        "invalid_count": len(failures),
        "record_count": len(results),
        "service": args.service_url,
        "status_counts": dict(sorted(status_counts.items())),
        "valid_count": len(results) - len(failures),
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(json.dumps(report, indent=2, sort_keys=True))
    return int(bool(failures))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("records_root", type=Path)
    result.add_argument("--service-url", default="http://127.0.0.1:8111")
    result.add_argument("--collection", default="research_info")
    result.add_argument("--token", default="preview-validator")
    result.add_argument("--report", type=Path)
    return result


if __name__ == "__main__":
    raise SystemExit(run(parser().parse_args()))
