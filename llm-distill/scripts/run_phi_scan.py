#!/usr/bin/env python3
"""Scan candidate corpus files for PHI/PII-like patterns without printing values."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


PATTERNS = {
    "ssn_like": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "phone_like": re.compile(r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),
    "email_like": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "dob_label": re.compile(r"\b(?:DOB|date of birth)\b", re.IGNORECASE),
    "member_id_label": re.compile(
        r"\b(?:member id|subscriber id|policy number|policy #|member #)\b",
        re.IGNORECASE,
    ),
    "claim_number_label": re.compile(r"\b(?:claim number|claim #|ICN|DCN)\b", re.IGNORECASE),
    "mrn_label": re.compile(r"\b(?:MRN|medical record number)\b", re.IGNORECASE),
    "patient_name_label": re.compile(r"\b(?:patient|member)\s*(?:name)?\s*:", re.IGNORECASE),
    "street_address_like": re.compile(
        r"\b\d{2,6}\s+[A-Z0-9][A-Z0-9.'-]*(?:\s+[A-Z0-9][A-Z0-9.'-]*){0,4}\s+"
        r"(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|boulevard|blvd)\b",
        re.IGNORECASE,
    ),
}


def scan_text(path: Path, text: str) -> list[dict]:
    findings: list[dict] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for finding_type, pattern in PATTERNS.items():
            for match in pattern.finditer(line):
                findings.append(
                    {
                        "path": str(path),
                        "line": line_number,
                        "column": match.start() + 1,
                        "finding_type": finding_type,
                    }
                )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    findings: list[dict] = []
    for path in args.paths:
        if path.is_dir():
            candidates = sorted(p for p in path.rglob("*") if p.is_file())
        else:
            candidates = [path]
        for candidate in candidates:
            try:
                text = candidate.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            findings.extend(scan_text(candidate, text))

    if args.json:
        print(json.dumps({"findings": findings}, indent=2))
    else:
        for finding in findings:
            print(
                f"{finding['path']}:{finding['line']}:"
                f"{finding['column']}:{finding['finding_type']}"
            )
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
