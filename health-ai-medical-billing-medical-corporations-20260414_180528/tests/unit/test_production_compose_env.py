import re
from pathlib import Path

from app.core.config import Settings


APP_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = APP_ROOT / "docker-compose.production.yml"

REQUIRED_GUARD_ENV_VARS = {
    "CLAIMGUARD_STUDENT_USE_BY_DEFAULT",
    "CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED",
    "CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE",
    "CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED",
    "CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA",
    "CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH",
    "USER_DATA_MODEL_IMPROVEMENT_ENABLED",
    "USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED",
    "USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED",
    "USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION",
    "USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE",
    "USER_DATA_MODEL_IMPROVEMENT_EVIDENCE_REPORT",
    "PREDICTION_FAIRNESS_EVIDENCE_REPORT",
    "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ENABLED",
    "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ROLLBACK_TO_MANUAL",
    "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_EVIDENCE_REPORT",
    "RETRIEVAL_EMBEDDING_BACKEND",
    "RETRIEVAL_EMBEDDING_MODEL",
    "RETRIEVAL_EMBEDDING_MODEL_APPROVED",
    "RETRIEVAL_VECTOR_BACKEND",
    "RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED",
    "RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION",
}


def _api_environment_values() -> dict[str, str]:
    text = COMPOSE_PATH.read_text(encoding="utf-8")
    in_api = False
    in_environment = False
    values: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith("  api:"):
            in_api = True
            continue
        if in_api and line.startswith("  frontend:"):
            break
        if in_api and line.strip() == "environment:":
            in_environment = True
            continue
        if in_environment and re.match(r"^    [a-z_]+:", line):
            break
        if not in_environment:
            continue
        match = re.match(r"^\s{6}([A-Z0-9_]+):\s*(.*)$", line)
        if match:
            values[match.group(1)] = match.group(2)
    return values


def test_production_compose_exposes_startup_guard_settings():
    env_values = _api_environment_values()
    settings_fields = set(Settings.model_fields)

    assert REQUIRED_GUARD_ENV_VARS <= settings_fields
    assert REQUIRED_GUARD_ENV_VARS <= set(env_values)


def test_production_compose_keeps_gate_defaults_conservative():
    env_values = _api_environment_values()

    assert env_values["CLAIMGUARD_STUDENT_USE_BY_DEFAULT"].endswith(":-false}")
    assert env_values["CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED"].endswith(":-false}")
    assert env_values["CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED"].endswith(":-false}")
    assert env_values["CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA"].endswith(":-true}")
    assert env_values["CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH"].endswith(":-false}")
    assert env_values["USER_DATA_MODEL_IMPROVEMENT_ENABLED"].endswith(":-false}")
    assert env_values["USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED"].endswith(":-false}")
    assert env_values["USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED"].endswith(":-false}")
    assert env_values["CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ENABLED"].endswith(":-false}")
    assert env_values["CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ROLLBACK_TO_MANUAL"].endswith(":-true}")
    assert env_values["RETRIEVAL_EMBEDDING_BACKEND"].endswith(":-hash}")
    assert env_values["RETRIEVAL_VECTOR_BACKEND"].endswith(":-encrypted_local_metadata}")
    assert env_values["RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED"].endswith(":-false}")
    assert env_values["RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION"].endswith(":-false}")


def test_production_compose_does_not_use_unconsumed_model_improvement_alias():
    env_values = _api_environment_values()

    assert "CLAIMGUARD_ALLOW_MODEL_IMPROVEMENT" not in env_values
