import json
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = APP_ROOT / "frontend"


def _read_frontend(path: str) -> str:
    return (FRONTEND_ROOT / path).read_text(encoding="utf-8")


def test_frontend_uses_dompurify_for_untrusted_text_rendering():
    package_json = json.loads((FRONTEND_ROOT / "package.json").read_text(encoding="utf-8"))
    safe_html_util = _read_frontend("src/utils/safeHtml.ts")
    safe_html_component = _read_frontend("src/components/common/SafeHtml.tsx")

    assert "dompurify" in package_json["dependencies"]
    assert "import DOMPurify from 'dompurify'" in safe_html_util
    assert "DOMPurify.sanitize" in safe_html_util
    assert "ALLOWED_TAGS: ['br']" in safe_html_util
    assert "ALLOWED_ATTR: []" in safe_html_util
    assert "dangerouslySetInnerHTML" in safe_html_component


def test_direct_html_insertion_is_isolated_to_safe_html_component():
    html_insertion_markers = (
        "dangerouslySetInnerHTML",
        ".innerHTML",
        "insertAdjacentHTML",
    )
    allowed_file = FRONTEND_ROOT / "src/components/common/SafeHtml.tsx"

    for path in (FRONTEND_ROOT / "src").rglob("*"):
        if path.suffix not in {".ts", ".tsx", ".js", ".jsx"}:
            continue

        content = path.read_text(encoding="utf-8")
        for marker in html_insertion_markers:
            if marker not in content:
                continue
            assert path == allowed_file, f"{marker} is only allowed in SafeHtml.tsx"


def test_high_risk_model_outputs_render_through_safe_html_component():
    claims_page = _read_frontend("src/pages/Claims.tsx")
    dashboard_page = _read_frontend("src/pages/Dashboard.tsx")
    appeals_page = _read_frontend("src/pages/Appeals.tsx")
    denial_workflow_page = _read_frontend("src/pages/DenialWorkflow.tsx")

    assert "import SafeHtml" in claims_page
    assert "value={docResult.analysis}" in claims_page
    assert "value={docResult.appeal_strategy}" in claims_page

    assert "import SafeHtml" in dashboard_page
    assert "value={selectedClaim.claim_data.ai_analysis}" in dashboard_page
    assert "value={selectedClaim.claim_data.appeal_strategy}" in dashboard_page
    assert "value={documentContent.document_text}" in dashboard_page

    assert "import SafeHtml" in appeals_page
    assert "value={result.appeal_letter}" in appeals_page

    assert "import SafeHtml" in denial_workflow_page
    assert "value={workflow.case_summary}" in denial_workflow_page
    assert "value={workflow.appeal_strategy}" in denial_workflow_page
    assert "value={deidentifyResult.deidentified_text}" in denial_workflow_page
