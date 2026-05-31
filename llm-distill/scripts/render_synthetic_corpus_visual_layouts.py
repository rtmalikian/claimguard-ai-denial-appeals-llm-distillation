#!/usr/bin/env python3
"""Render CSS-styled HTML companions for the synthetic denial/appeal corpus."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
DISTILL_DIR = REPO_ROOT / "llm-distill"
DEFAULT_CORPUS_DIR = DISTILL_DIR / "data" / "corpus" / "generated_synthetic_pairs"
DEFAULT_MANIFEST = DEFAULT_CORPUS_DIR / "manifest_synthetic_900.json"
DEFAULT_VISUAL_MANIFEST = DEFAULT_CORPUS_DIR / "visual_manifest_synthetic_900.json"
DEFAULT_REPORT = DEFAULT_CORPUS_DIR / "visual_render_report.json"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_phi_scan import scan_text  # noqa: E402


TYPOGRAPHY_STYLES: dict[str, dict[str, str | int]] = {
    "serif_notice_body": {
        "font_family": "Georgia, Times New Roman, serif",
        "heading_family": "Georgia, Times New Roman, serif",
        "font_size_px": 15,
    },
    "sans_serif_portal_body": {
        "font_family": "Arial, Helvetica, sans-serif",
        "heading_family": "Arial, Helvetica, sans-serif",
        "font_size_px": 14,
    },
    "monospace_fax_extract": {
        "font_family": "Courier New, Courier, monospace",
        "heading_family": "Courier New, Courier, monospace",
        "font_size_px": 13,
    },
    "condensed_table_labels": {
        "font_family": "Arial Narrow, Roboto Condensed, Arial, sans-serif",
        "heading_family": "Arial Narrow, Roboto Condensed, Arial, sans-serif",
        "font_size_px": 13,
    },
    "large_print_accessible_notice": {
        "font_family": "Verdana, Arial, sans-serif",
        "heading_family": "Verdana, Arial, sans-serif",
        "font_size_px": 18,
    },
    "small_footer_legal_notice": {
        "font_family": "Times New Roman, Georgia, serif",
        "heading_family": "Times New Roman, Georgia, serif",
        "font_size_px": 12,
    },
    "mixed_heading_body_hierarchy": {
        "font_family": "Calibri, Arial, sans-serif",
        "heading_family": "Georgia, Times New Roman, serif",
        "font_size_px": 14,
    },
    "plain_text_eob_export": {
        "font_family": "Lucida Console, Courier New, monospace",
        "heading_family": "Lucida Console, Courier New, monospace",
        "font_size_px": 13,
    },
}

LAYOUT_STYLES: dict[str, dict[str, str | int]] = {
    "single_column_letterhead": {"class_name": "layout-letterhead", "page_width_px": 760},
    "two_column_eob_summary": {"class_name": "layout-two-column", "page_width_px": 920},
    "portal_card_stack": {"class_name": "layout-portal-cards", "page_width_px": 820},
    "dense_utilization_review_notice": {"class_name": "layout-dense-review", "page_width_px": 780},
    "fax_cover_plus_body": {"class_name": "layout-fax", "page_width_px": 760},
    "tabbed_reconsideration_notice": {"class_name": "layout-tabbed", "page_width_px": 840},
    "bullet_heavy_managed_care_notice": {"class_name": "layout-managed-care", "page_width_px": 820},
    "employer_plan_memo": {"class_name": "layout-memo", "page_width_px": 800},
    "records_index_packet": {"class_name": "layout-records-index", "page_width_px": 860},
    "short_portal_update": {"class_name": "layout-short-portal", "page_width_px": 700},
    "long_form_adverse_benefit_notice": {"class_name": "layout-long-form", "page_width_px": 780},
    "corrected_claim_cover_layout": {"class_name": "layout-corrected-claim", "page_width_px": 800},
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w-]+\b", text))


def manifest_source_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def resolve_source_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


def manifest_records(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    raw_records = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(raw_records, list):
        raise ValueError("manifest JSON must be a list or an object with records")
    records = [record for record in raw_records if isinstance(record, dict)]
    if len(records) != len(raw_records):
        raise ValueError("manifest records must all be objects")
    return records


def html_body(text: str) -> str:
    blocks: list[str] = []
    for raw_block in re.split(r"\n{2,}", text.strip()):
        escaped = html.escape(raw_block)
        if "\n|" in "\n" + raw_block or raw_block.strip().startswith("|"):
            blocks.append(f"<pre class=\"table-block\">{escaped}</pre>")
        elif raw_block.strip().startswith("- ") or "\n-" in raw_block:
            lines = [line.strip() for line in raw_block.splitlines() if line.strip()]
            lead = []
            items = []
            for line in lines:
                if line.startswith("- "):
                    items.append(f"<li>{html.escape(line[2:])}</li>")
                else:
                    lead.append(html.escape(line))
            prefix = "".join(f"<p>{line}</p>" for line in lead)
            blocks.append(f"{prefix}<ul>{''.join(items)}</ul>")
        else:
            blocks.append(f"<p>{escaped.replace(chr(10), '<br>')}</p>")
    return "\n".join(blocks)


def render_html_document(record: dict[str, Any], text: str) -> str:
    typography_profile = str(record.get("typography_profile") or "sans_serif_portal_body")
    layout_profile = str(record.get("layout_profile") or "single_column_letterhead")
    typography = TYPOGRAPHY_STYLES.get(typography_profile, TYPOGRAPHY_STYLES["sans_serif_portal_body"])
    layout = LAYOUT_STYLES.get(layout_profile, LAYOUT_STYLES["single_column_letterhead"])
    font_family = str(typography["font_family"])
    heading_family = str(typography["heading_family"])
    font_size = int(typography["font_size_px"])
    page_width = int(layout["page_width_px"])
    class_name = str(layout["class_name"])
    title = html.escape(str(record.get("document_id") or "synthetic document"))
    role = html.escape(str(record.get("document_role") or "synthetic_role"))
    pair_id = html.escape(str(record.get("pair_id") or "synthetic_pair"))
    format_profile = html.escape(str(record.get("format_profile") or "synthetic_format"))
    escaped_layout = html.escape(layout_profile)
    escaped_typography = html.escape(typography_profile)
    escaped_font = html.escape(font_family)
    escaped_checksum = html.escape(sha256_text(text))
    body = html_body(text)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="synthetic-corpus" content="ClaimGuard generated synthetic no-PHI letter">
  <meta name="text-checksum" content="{escaped_checksum}">
  <title>{title}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1d2733;
      --muted: #52606d;
      --line: #c9d1d9;
      --paper: #ffffff;
      --band: #eef2f5;
    }}
    body {{
      margin: 0;
      background: #edf0f3;
      color: var(--ink);
      font-family: {font_family};
      font-size: {font_size}px;
      line-height: 1.52;
    }}
    .page {{
      width: min({page_width}px, calc(100vw - 48px));
      margin: 24px auto;
      background: var(--paper);
      border: 1px solid var(--line);
      padding: 34px;
      box-sizing: border-box;
    }}
    .visual-profile {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px 18px;
      padding: 12px 14px;
      margin-bottom: 22px;
      border: 1px solid var(--line);
      background: var(--band);
      font-size: 12px;
    }}
    h1 {{
      margin: 0 0 12px;
      font-family: {heading_family};
      font-size: {font_size + 8}px;
      line-height: 1.16;
      font-weight: 700;
    }}
    p {{ margin: 0 0 12px; }}
    ul {{ margin: 0 0 14px 22px; padding: 0; }}
    .table-block {{
      white-space: pre-wrap;
      border: 1px solid var(--line);
      background: #f7f8fa;
      padding: 10px;
      overflow-wrap: anywhere;
    }}
    .layout-two-column .document-body,
    .layout-records-index .document-body {{
      column-count: 2;
      column-gap: 34px;
    }}
    .layout-portal-cards .document-body p,
    .layout-short-portal .document-body p {{
      border: 1px solid var(--line);
      padding: 10px;
      background: #fbfcfd;
    }}
    .layout-dense-review {{
      padding: 24px;
      line-height: 1.36;
    }}
    .layout-fax {{
      border-style: dashed;
      font-family: Courier New, Courier, monospace;
    }}
    .layout-tabbed h1,
    .layout-corrected-claim h1 {{
      border-bottom: 5px solid var(--line);
      padding-bottom: 8px;
    }}
    .layout-managed-care ul {{
      list-style-type: square;
    }}
    .layout-memo .visual-profile {{
      border-left: 7px solid var(--muted);
    }}
    .layout-long-form {{
      padding: 42px;
    }}
  </style>
</head>
<body>
  <main class="page {class_name}"
    data-layout-profile="{escaped_layout}"
    data-typography-profile="{escaped_typography}"
    data-font-family="{escaped_font}">
    <h1>{title}</h1>
    <section class="visual-profile" aria-label="Synthetic visual profile">
      <div><strong>Role:</strong> {role}</div>
      <div><strong>Pair:</strong> {pair_id}</div>
      <div><strong>Format:</strong> {format_profile}</div>
      <div><strong>Layout:</strong> {escaped_layout}</div>
      <div><strong>Typography:</strong> {escaped_typography}</div>
      <div><strong>Font stack:</strong> {escaped_font}</div>
    </section>
    <section class="document-body">
{body}
    </section>
  </main>
</body>
</html>
"""


def render_visual_layouts(
    *,
    corpus_dir: Path,
    manifest_path: Path,
    visual_manifest_path: Path,
    report_path: Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    records = manifest_records(manifest_path)
    visual_records: list[dict[str, Any]] = []
    blockers: list[str] = []
    phi_findings: list[dict[str, Any]] = []
    counts: dict[str, Counter[str]] = {
        "document_role": Counter(),
        "split": Counter(),
        "layout_profile": Counter(),
        "typography_profile": Counter(),
        "font_family": Counter(),
    }
    missing_source_count = 0
    checksum_mismatch_count = 0
    html_existing_count = 0

    for record in records:
        document_id = str(record.get("document_id") or "unknown_document")
        source_path_raw = record.get("source_url_or_path")
        if not isinstance(source_path_raw, str) or not source_path_raw:
            blockers.append(f"{document_id}: source_url_or_path is required")
            missing_source_count += 1
            continue
        source_path = resolve_source_path(source_path_raw)
        if not source_path.exists():
            blockers.append(f"{document_id}: source text missing")
            missing_source_count += 1
            continue
        text = source_path.read_text(encoding="utf-8")
        if sha256_text(text) != record.get("checksum"):
            blockers.append(f"{document_id}: source checksum mismatch")
            checksum_mismatch_count += 1
        split = str(record.get("split") or "unknown_split")
        html_dir = corpus_dir / "rendered_html" / split
        html_dir.mkdir(parents=True, exist_ok=True)
        html_path = html_dir / f"{source_path.stem}.html"
        if html_path.exists() and not overwrite:
            blockers.append(f"{document_id}: rendered HTML already exists; pass --overwrite to refresh")
            html_existing_count += 1
            continue
        rendered = render_html_document(record, text)
        html_path.write_text(rendered, encoding="utf-8")
        phi_findings.extend(scan_text(html_path, rendered))

        typography_profile = str(record.get("typography_profile") or "sans_serif_portal_body")
        typography = TYPOGRAPHY_STYLES.get(typography_profile, TYPOGRAPHY_STYLES["sans_serif_portal_body"])
        font_family = str(typography["font_family"])
        layout_profile = str(record.get("layout_profile") or "single_column_letterhead")
        role = str(record.get("document_role") or "unknown_role")
        counts["document_role"][role] += 1
        counts["split"][split] += 1
        counts["layout_profile"][layout_profile] += 1
        counts["typography_profile"][typography_profile] += 1
        counts["font_family"][font_family] += 1
        visual_records.append(
            {
                "document_id": document_id,
                "pair_id": record.get("pair_id"),
                "document_role": role,
                "split": split,
                "source_text_path": source_path_raw,
                "source_text_checksum": sha256_text(text),
                "rendered_html_path": manifest_source_path(html_path),
                "rendered_html_checksum": sha256_text(rendered),
                "layout_profile": layout_profile,
                "typography_profile": typography_profile,
                "font_family": font_family,
                "format_profile": record.get("format_profile"),
                "word_count": word_count(text),
                "synthetic_only": True,
                "real_patient_data_used": False,
                "real_claim_data_used": False,
            }
        )

    visual_manifest = {
        "version": "synthetic-large-900-visual-layouts",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_manifest": manifest_source_path(manifest_path),
        "records": visual_records,
    }
    visual_manifest_path.write_text(
        json.dumps(visual_manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    pair_ids = {record.get("pair_id") for record in visual_records if record.get("pair_id")}
    report = {
        "artifact": "synthetic_denial_appeal_visual_layouts",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ready": not blockers and not phi_findings and len(visual_records) == len(records),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "evidence": {
            "corpus_dir": str(corpus_dir),
            "source_manifest": str(manifest_path),
            "visual_manifest": str(visual_manifest_path),
            "source_record_count": len(records),
            "visual_record_count": len(visual_records),
            "pair_count": len(pair_ids),
            "letter_count": len(visual_records),
            "rendered_html_count": len(visual_records),
            "missing_source_count": missing_source_count,
            "checksum_mismatch_count": checksum_mismatch_count,
            "html_existing_count": html_existing_count,
            "counts": {key: dict(sorted(value.items())) for key, value in counts.items()},
            "variant_counts": {
                "font_family": len(counts["font_family"]),
                "layout_profile": len(counts["layout_profile"]),
                "typography_profile": len(counts["typography_profile"]),
            },
            "phi_scan": {
                "finding_count": len(phi_findings),
                "finding_types": sorted(
                    {str(finding.get("finding_type", "unknown")) for finding in phi_findings}
                ),
                "values_redacted": True,
            },
            "safety": {
                "external_model_calls_made": False,
                "synthetic_only": True,
                "real_patient_data_used": False,
                "real_claim_data_used": False,
                "actual_css_font_stacks": True,
                "actual_html_layout_wrappers": True,
            },
        },
        "notes": [
            "Rendered HTML companions preserve the same synthetic text as the training corpus.",
            "Actual CSS font-family stacks and layout classes provide visual document variation.",
            "HTML files are local no-PHI artifacts for layout and OCR-style stress testing.",
        ],
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--visual-manifest", type=Path, default=DEFAULT_VISUAL_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()

    report = render_visual_layouts(
        corpus_dir=args.corpus_dir,
        manifest_path=args.manifest,
        visual_manifest_path=args.visual_manifest,
        report_path=args.output,
        overwrite=args.overwrite,
    )
    print(f"wrote synthetic visual layout report to {args.output}")
    if args.fail_on_blocked and not report["ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
