#!/usr/bin/env python3
"""Validate and print the ClaimGuard distillation source registry.

This script does not download content. Downloading or scraping public sources
must happen only after license, terms, and PHI-screening review.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_FIELDS = {
    "source_id",
    "title",
    "url",
    "source_type",
    "tier",
    "phi_status",
    "license_status",
}


def load_registry(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Source registry must be a JSON array")
    return data


def validate_registry(sources: list[dict]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for index, source in enumerate(sources, start=1):
        missing = sorted(REQUIRED_FIELDS - set(source))
        if missing:
            errors.append(f"row {index}: missing fields {', '.join(missing)}")
        source_id = source.get("source_id")
        if source_id in seen:
            errors.append(f"row {index}: duplicate source_id {source_id}")
        if source_id:
            seen.add(source_id)
        if source.get("tier") not in {1, 2, 3}:
            errors.append(f"row {index}: tier must be 1, 2, or 3")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "source_registry.json",
    )
    parser.add_argument("--json", action="store_true", help="Print registry JSON")
    args = parser.parse_args()

    sources = load_registry(args.registry)
    errors = validate_registry(sources)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    if args.json:
        print(json.dumps(sources, indent=2))
    else:
        for source in sources:
            print(
                f"{source['source_id']}\tT{source['tier']}\t"
                f"{source['source_type']}\t{source['title']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
