#!/usr/bin/env python3
"""Normalize text files into source chunks for retrieval/eval experiments."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    output: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + chunk_size)
        output.append(normalized[start:end].strip())
        if end == len(normalized):
            break
        start = max(0, end - overlap)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-type", default="public_document")
    parser.add_argument("--phi-status", default="needs_scan")
    parser.add_argument("--license-status", default="review_required")
    parser.add_argument("--chunk-size", type=int, default=900)
    parser.add_argument("--overlap", type=int, default=120)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for input_path in args.inputs:
            text = input_path.read_text(encoding="utf-8")
            for index, chunk_text in enumerate(
                chunks(text, args.chunk_size, args.overlap),
                start=1,
            ):
                record = {
                    "chunk_id": f"{input_path.stem}-chunk-{index:03d}",
                    "source_id": input_path.stem,
                    "title": input_path.name,
                    "source_type": args.source_type,
                    "text": chunk_text,
                    "phi_status": args.phi_status,
                    "license_status": args.license_status,
                }
                handle.write(json.dumps(record) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
