#!/usr/bin/env python3
"""Sanitize source-controlled report output without changing gate logic."""

from __future__ import annotations

import re
import json
from pathlib import Path
from typing import Any


EXTERNAL_PATH_REDACTION = "external_path_redacted"
LOCAL_ABSOLUTE_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_])/(?:Users|private|tmp|var|Volumes)/[^\s\"']+"
)


def sanitize_report_string(value: str, repo_root: Path) -> str:
    root = str(repo_root.resolve())
    sanitized = value.replace(root + "/", "")
    if sanitized == root:
        return "."
    return LOCAL_ABSOLUTE_PATH_RE.sub(EXTERNAL_PATH_REDACTION, sanitized)


def sanitize_report_value(value: Any, repo_root: Path) -> Any:
    if isinstance(value, str):
        return sanitize_report_string(value, repo_root)
    if isinstance(value, list):
        return [sanitize_report_value(item, repo_root) for item in value]
    if isinstance(value, dict):
        return {
            key: sanitize_report_value(item, repo_root)
            for key, item in value.items()
        }
    return value


def write_sanitized_report_json(
    path: Path,
    payload: Any,
    repo_root: Path,
    *,
    sort_keys: bool = True,
) -> None:
    safe_payload = sanitize_report_value(payload, repo_root)
    path.write_text(
        json.dumps(safe_payload, indent=2, sort_keys=sort_keys) + "\n",
        encoding="utf-8",
    )
