from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.limiter import limiter
from app.db.database import init_db
from app.api.v1 import claims, analytics, appeals, patients, auth, denial_workflow, monitoring
from app.middleware.auth import JWTAuthMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.services.nvidia import validate_nvidia_startup_config
from app.utils.backup_disaster_recovery_config import (
    validate_backup_disaster_recovery_startup_config,
)
from app.utils.clearinghouse_submission_config import (
    validate_clearinghouse_submission_startup_config,
)
from app.utils.dependency_security_config import (
    validate_dependency_security_startup_config,
)
from app.utils.model_improvement import validate_model_improvement_startup_config
from app.utils.prediction_fairness_config import validate_prediction_fairness_startup_config
from app.utils.retrieval_vector_config import validate_retrieval_vector_startup_config
from app.utils.student_default_config import validate_student_default_startup_config
from app.utils.error_responses import (
    http_exception_handler,
    rate_limit_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)

app = FastAPI(
    title=settings.APP_NAME,
    description="Medical Billing Claim Denial Prediction & Prevention System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.add_middleware(JWTAuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)

app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(claims.router, prefix=settings.API_V1_PREFIX)
app.include_router(analytics.router, prefix=settings.API_V1_PREFIX)
app.include_router(appeals.router, prefix=settings.API_V1_PREFIX)
app.include_router(patients.router, prefix=settings.API_V1_PREFIX)
app.include_router(denial_workflow.router, prefix=settings.API_V1_PREFIX)
app.include_router(monitoring.router, prefix=settings.API_V1_PREFIX)


@app.on_event("startup")
async def startup_event():
    init_db()
    validate_nvidia_startup_config()
    validate_model_improvement_startup_config()
    validate_prediction_fairness_startup_config()
    validate_backup_disaster_recovery_startup_config()
    validate_dependency_security_startup_config()
    validate_clearinghouse_submission_startup_config()
    validate_retrieval_vector_startup_config()
    from app.services.denial_workflow import DenialWorkflowService

    student_status = None
    if settings.CLAIMGUARD_STUDENT_USE_BY_DEFAULT:
        runtime_health = await DenialWorkflowService.student_runtime_health()
        student_status = DenialWorkflowService.student_model_status(
            runtime_health=runtime_health
        )
    validate_student_default_startup_config(student_status=student_status)


@app.get("/health")
async def health_check():
    from sqlalchemy import text
    from app.db.database import engine
    from app.services.ocr import OcrService
    from app.services.nvidia import nvidia_service
    from app.services.llm_provider import get_configured_llm_service
    from app.services.denial_workflow import DenialWorkflowService
    health = {"status": "healthy", "service": settings.APP_NAME, "checks": {}}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        health["checks"]["database"] = "ok"
    except Exception as e:
        health["checks"]["database"] = f"error: {str(e)}"
        health["status"] = "degraded"

    nvidia_health = await nvidia_service.health_check()
    health["checks"]["nvidia"] = nvidia_health
    if nvidia_health.get("status") != "ok":
        health["status"] = "degraded"

    ocr_health = await OcrService().health_check()
    health["checks"]["ocr"] = ocr_health
    if ocr_health.get("status") != "ok":
        health["status"] = "degraded"

    llm_health = await get_configured_llm_service().health_check()
    health["checks"]["configured_llm"] = llm_health
    if settings.LLM_PROVIDER == "mlx_lm" and llm_health.get("status") != "ok":
        health["status"] = "degraded"

    student_runtime = await DenialWorkflowService.student_runtime_health()
    student_status = DenialWorkflowService.student_model_status(runtime_health=student_runtime)
    health["checks"]["claim_guard_student"] = student_status.model_dump(mode="json")
    if (
        settings.CLAIMGUARD_STUDENT_USE_BY_DEFAULT
        and not student_status.default_cutover_ready
        and not student_status.rollback_to_nvidia_enabled
    ):
        health["status"] = "degraded"

    return health


@app.get("/")
async def root():
    return {"message": "ClaimGuard AI API", "version": "1.0.0", "docs": "/docs"}
