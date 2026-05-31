"""Local CARC/RARC lifecycle seed database utilities.

The bundled JSON stores only code lifecycle metadata and internal categories.
It intentionally excludes official long-form descriptions and is not a
production substitute for a licensed X12 code-list update process.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from typing import Any


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "carc_rarc_codes.json"
ACTIVE_STATUS = "active"
INACTIVE_STATUS = "inactive"
FORMAT_VALID_UNCONFIRMED_STATUS = "format_valid_unconfirmed"
INVALID_FORMAT_STATUS = "invalid_format"


@dataclass(frozen=True)
class CarcRarcCodeRecord:
    """Safe lifecycle metadata for one external code-list entry."""

    list_id: str
    code: str
    status: str
    category: str | None = None
    stop_date: str | None = None
    replacement: str | None = None

    @property
    def is_active(self) -> bool:
        return self.status == ACTIVE_STATUS

    def safe_metadata(self) -> dict[str, str | bool | None]:
        return {
            "list_id": self.list_id,
            "status": self.status,
            "category": self.category,
            "record_found": True,
            "stop_date": self.stop_date,
            "replacement": self.replacement,
            "official_description_included": False,
        }


@dataclass(frozen=True)
class CarcRarcLookup:
    """Safe lookup result without raw code descriptions."""

    list_id: str
    status: str
    category: str | None = None
    record_found: bool = False
    stop_date: str | None = None
    replacement: str | None = None
    source_last_checked: str | None = None
    schema_version: str | None = None

    @property
    def allows_code(self) -> bool:
        return self.status in {ACTIVE_STATUS, FORMAT_VALID_UNCONFIRMED_STATUS}

    def safe_metadata(self) -> dict[str, str | bool | None]:
        return {
            "list_id": self.list_id,
            "status": self.status,
            "category": self.category,
            "record_found": self.record_found,
            "stop_date": self.stop_date,
            "replacement": self.replacement,
            "source_last_checked": self.source_last_checked,
            "schema_version": self.schema_version,
            "official_description_included": False,
            "raw_code_value_included": False,
        }


@dataclass(frozen=True)
class CarcRarcCodeDatabase:
    """Loaded local CARC/RARC seed database."""

    schema_version: str
    source_last_checked: str
    source_urls: dict[str, str]
    carc_reason_codes: dict[str, CarcRarcCodeRecord]
    rarc_codes: dict[str, CarcRarcCodeRecord]

    def summary(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "source_last_checked": self.source_last_checked,
            "source_urls": dict(self.source_urls),
            "carc_seed_count": len(self.carc_reason_codes),
            "rarc_seed_count": len(self.rarc_codes),
            "official_descriptions_included": False,
            "comprehensive_code_list": False,
        }


def normalize_external_code(value: object) -> str:
    return str(value or "").strip().replace(" ", "").upper()


@lru_cache(maxsize=1)
def load_carc_rarc_code_database() -> CarcRarcCodeDatabase:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return CarcRarcCodeDatabase(
        schema_version=str(payload["schema_version"]),
        source_last_checked=str(payload["source_last_checked"]),
        source_urls=dict(payload.get("source_urls", {})),
        carc_reason_codes=_build_index("CARC", payload.get("carc_reason_codes", [])),
        rarc_codes=_build_index("RARC", payload.get("rarc_codes", [])),
    )


def get_carc_reason_code_record(value: object) -> CarcRarcCodeRecord | None:
    code = normalize_external_code(value)
    return load_carc_rarc_code_database().carc_reason_codes.get(code)


def get_rarc_code_record(value: object) -> CarcRarcCodeRecord | None:
    code = normalize_external_code(value)
    return load_carc_rarc_code_database().rarc_codes.get(code)


def resolve_carc_reason_code(
    value: object, *, format_valid: bool
) -> CarcRarcLookup:
    return _resolve_code(
        value,
        list_id="CARC",
        format_valid=format_valid,
        record=get_carc_reason_code_record(value),
    )


def resolve_rarc_code(value: object, *, format_valid: bool) -> CarcRarcLookup:
    return _resolve_code(
        value,
        list_id="RARC",
        format_valid=format_valid,
        record=get_rarc_code_record(value),
    )


def _build_index(
    list_id: str, records: list[dict[str, Any]]
) -> dict[str, CarcRarcCodeRecord]:
    indexed: dict[str, CarcRarcCodeRecord] = {}
    for record in records:
        code = normalize_external_code(record.get("code"))
        if not code:
            continue
        if code in indexed:
            raise ValueError(f"Duplicate {list_id} seed code: {code}")
        indexed[code] = CarcRarcCodeRecord(
            list_id=list_id,
            code=code,
            status=str(record.get("status") or ""),
            category=record.get("category"),
            stop_date=record.get("stop_date"),
            replacement=record.get("replacement"),
        )
    return indexed


def _resolve_code(
    value: object,
    *,
    list_id: str,
    format_valid: bool,
    record: CarcRarcCodeRecord | None,
) -> CarcRarcLookup:
    database = load_carc_rarc_code_database()
    if not format_valid:
        return CarcRarcLookup(
            list_id=list_id,
            status=INVALID_FORMAT_STATUS,
            source_last_checked=database.source_last_checked,
            schema_version=database.schema_version,
        )

    if record is None:
        return CarcRarcLookup(
            list_id=list_id,
            status=FORMAT_VALID_UNCONFIRMED_STATUS,
            source_last_checked=database.source_last_checked,
            schema_version=database.schema_version,
        )

    return CarcRarcLookup(
        list_id=list_id,
        status=record.status,
        category=record.category,
        record_found=True,
        stop_date=record.stop_date,
        replacement=record.replacement,
        source_last_checked=database.source_last_checked,
        schema_version=database.schema_version,
    )
