#!/usr/bin/env python3
"""Sanitize checked-in eval report JSON files for public source control."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_DIR = REPO_ROOT / "llm-distill" / "evals" / "reports"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from report_output_sanitizer import sanitize_report_value  # noqa: E402


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def report_paths(paths: list[Path] | None) -> list[Path]:
    if paths:
        return sorted({path.resolve() for path in paths})
    return sorted(DEFAULT_REPORT_DIR.glob("*.json"))


def sanitize_report_file(path: Path, *, check: bool = False) -> bool:
    payload = load_json(path)
    sanitized = sanitize_report_value(payload, REPO_ROOT)
    if sanitized == payload:
        return False
    if not check:
        path.write_text(json.dumps(sanitized, indent=2) + "\n", encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if any report would be changed.",
    )
    args = parser.parse_args()

    changed: list[str] = []
    for path in report_paths(args.paths):
        if not path.exists() or not path.is_file():
            raise SystemExit(f"missing report file: {path}")
        if sanitize_report_file(path, check=args.check):
            changed.append(str(path.relative_to(REPO_ROOT)))

    action = "would_update" if args.check else "updated"
    print(
        json.dumps(
            {
                "checked_count": len(report_paths(args.paths)),
                "changed_count": len(changed),
                action: changed,
            },
            indent=2,
        )
    )
    return 1 if args.check and changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
