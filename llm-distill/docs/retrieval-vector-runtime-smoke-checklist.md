# Retrieval Vector Runtime Smoke Checklist

ClaimGuard AI is architected by Raphael Malikian <rtmalikian@gmail.com>.

Current status: not runtime-smoked for production.

This checklist is a source-controlled operator procedure for runtime smoke
validation after private semantic embedding and vector-store configuration is
complete. It records procedure coverage only. Do not add PHI, production
document text, embedding vectors, credentials, service URLs, approval
references, or raw retrieval results to this file.

## Required Preconditions

- approved semantic embedding model required
- production vector backend required
- hash fallback disabled for production required
- private semantic provider loader configured with no source-controlled
  endpoint or token values required
- active retrieval chunks reindexed required
- stored hash embeddings absent required

## Runtime Smoke Steps

1. Confirm the private runtime uses the approved semantic embedding model and
   production vector backend through environment-controlled settings only.
2. Confirm `app/services/retrieval_semantic_provider.py` reports provider-ready
   status, HTTPS or loopback endpoint safety, configured dimensions, and no
   raw endpoint, token, source text, or vector values in logs.
3. Confirm hash fallback is disabled for production retrieval requests.
4. Confirm active retrieval chunks were reindexed after the final production
   embedding model and vector backend were selected.
5. Run a metadata-only vector backend health check.
6. Run a retrieval quality smoke check with synthetic or approved
   de-identified prompts only.
7. Confirm backup restore review required has been completed for vector-store
   metadata and indexes.
8. Confirm rollback or disable path required has been reviewed and can return
   retrieval to a conservative non-production-safe fallback.
9. Confirm metadata-only audit required captures status, timestamps, operator
   identity, and pass/fail states without source text or vector values.

## Evidence Rules

- vector backend health check required
- retrieval quality smoke check required
- backup restore review required
- rollback or disable path required
- metadata-only audit required
- boolean-only evidence
- no raw source text
- no raw vector values
- no embedding service URLs
- vector_backend_ready=false

Production vector backend readiness remains false until private runtime
configuration, reindexing, governance review, health checks, quality smoke
checks, and manual production-gate approval are complete outside source
control.
