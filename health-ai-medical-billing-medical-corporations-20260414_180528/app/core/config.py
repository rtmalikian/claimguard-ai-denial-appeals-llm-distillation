from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors_allowed_origins(raw_origins: str) -> list[str]:
    origins = [origin.strip().rstrip("/") for origin in raw_origins.split(",") if origin.strip()]
    if not origins:
        raise ValueError("CORS_ALLOWED_ORIGINS must include at least one origin")

    validated_origins = []
    for origin in origins:
        if origin == "*":
            raise ValueError("CORS_ALLOWED_ORIGINS cannot include wildcard '*'")

        parsed = urlparse(origin)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"Invalid CORS origin: {origin}")

        if parsed.path or parsed.params or parsed.query or parsed.fragment:
            raise ValueError(f"CORS origin must not include path, query, or fragment: {origin}")

        validated_origins.append(origin)

    return validated_origins


def parse_encryption_keys(raw_keys: str) -> list[str]:
    return [key.strip() for key in raw_keys.split(",") if key.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    DATABASE_URL: str = "postgresql://claimguard:secure_password@db:5432/claimguard"
    POSTGRES_USER: str = "claimguard"
    POSTGRES_PASSWORD: str = "secure_password"
    POSTGRES_DB: str = "claimguard"

    APP_ENV: str = "development"
    APP_NAME: str = "ClaimGuard AI"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    SECRET_KEY: str = "your-secret-key-change-in-production-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ENCRYPTION_KEYS: str = ""
    ENCRYPTION_KEY: str = ""
    BOOTSTRAP_ADMIN_EMAIL: str = ""
    BOOTSTRAP_ADMIN_PASSWORD: str = ""
    BOOTSTRAP_ADMIN_NAME: str = "Bootstrap Admin"
    BOOTSTRAP_ADMIN_SYNC_FROM_ENV: bool = False

    LLM_PROVIDER: str = "nvidia_nim"
    NVIDIA_API_KEY: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL: str = "nvidia/llama-3.3-nemotron-super-49b-v1.5"
    NVIDIA_OCR_MODEL: str = "nvidia/nemotron-parse"
    NVIDIA_TIMEOUT: int = 120
    MLX_BASE_URL: str = "http://localhost:8080/v1"
    MLX_MODEL: str = "Qwen/Qwen3-4B-MLX-4bit"
    MLX_FALLBACK_MODEL: str = "Qwen/Qwen3-1.7B"
    MLX_TIMEOUT: int = 120
    CLAIMGUARD_STUDENT_ADAPTER_PATH: str = (
        "llm-distill/models/adapters/claimguard-qwen3-4b-lora-reviewed"
    )
    CLAIMGUARD_STUDENT_SCHEMA_CONTRACT_NAME: str = "strict_claim_guard_json_v1"
    CLAIMGUARD_STUDENT_ACCEPTANCE_REPORT: str = (
        "llm-distill/evals/reports/student_acceptance_report.json"
    )
    CLAIMGUARD_STUDENT_READINESS_REPORT: str = (
        "llm-distill/evals/reports/distillation_readiness_audit_report.json"
    )
    CLAIMGUARD_STUDENT_BENCHMARK_REPORT: str = (
        "llm-distill/evals/reports/student_mlx_benchmark_report.json"
    )
    CLAIMGUARD_STUDENT_USE_BY_DEFAULT: bool = False
    CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED: bool = False
    CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE: str = ""
    CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED: bool = False
    CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA: bool = False
    CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH: bool = False
    CLAIMGUARD_STUDENT_MAX_TOKENS: int = 1800
    CLAIMGUARD_STUDENT_ENABLE_THINKING: bool = False
    USER_DATA_MODEL_IMPROVEMENT_ENABLED: bool = False
    USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED: bool = False
    USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED: bool = False
    USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION: str = ""
    USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE: str = ""
    USER_DATA_MODEL_IMPROVEMENT_EVIDENCE_REPORT: str = (
        "llm-distill/evals/reports/model_improvement_evidence_report.json"
    )
    PREDICTION_FAIRNESS_EVIDENCE_REPORT: str = (
        "llm-distill/evals/reports/prediction_fairness_evidence_report.json"
    )
    BACKUP_DISASTER_RECOVERY_EVIDENCE_REPORT: str = (
        "llm-distill/evals/reports/backup_disaster_recovery_evidence_report.json"
    )
    DEPENDENCY_SECURITY_EVIDENCE_REPORT: str = (
        "llm-distill/evals/reports/dependency_security_evidence_report.json"
    )
    CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ENABLED: bool = False
    CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ROLLBACK_TO_MANUAL: bool = True
    CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_EVIDENCE_REPORT: str = (
        "llm-distill/evals/reports/clearinghouse_submission_evidence_report.json"
    )
    RETRIEVAL_EMBEDDING_BACKEND: str = "hash"
    RETRIEVAL_EMBEDDING_MODEL: str = "claimguard-hash-embedding-v1"
    RETRIEVAL_EMBEDDING_MODEL_APPROVED: bool = False
    RETRIEVAL_VECTOR_BACKEND: str = "encrypted_local_metadata"
    RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED: bool = False
    RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION: bool = False
    RETRIEVAL_PRIVATE_EMBEDDING_URL: str = ""
    RETRIEVAL_PRIVATE_EMBEDDING_TOKEN: str = ""
    RETRIEVAL_PRIVATE_EMBEDDING_DIMENSIONS: int = 0
    RETRIEVAL_PRIVATE_EMBEDDING_TIMEOUT_SECONDS: int = 10

    OCR_ENGINE: str = "nvidia_nemotron_parse"
    OCR_TIMEOUT: int = 120
    OCR_MAX_PAGES: int = 10
    OCR_RENDER_DPI: int = 200
    OCR_MAX_DIMENSION: int = 2200

    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ALLOWED_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_allowed_origins(self) -> list[str]:
        return parse_cors_allowed_origins(self.CORS_ALLOWED_ORIGINS)

    @property
    def configured_encryption_keys(self) -> list[str]:
        if self.ENCRYPTION_KEYS.strip():
            return parse_encryption_keys(self.ENCRYPTION_KEYS)
        if self.ENCRYPTION_KEY.strip():
            return [self.ENCRYPTION_KEY.strip()]
        return []


settings = Settings()
