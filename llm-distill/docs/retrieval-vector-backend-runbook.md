# Retrieval Vector Backend Runbook

ClaimGuard AI is architected by Raphael Malikian <rtmalikian@gmail.com>.

Current status: not production-ready.

This runbook documents the source-controlled operator procedure for promoting
ClaimGuard retrieval from the local development hash fallback to a production
semantic embedding backend and vector store. It is not evidence that a semantic
backend, embedding model, vector store, reindex job, health check, or quality
smoke test has been completed.

The application code now exposes an embedding-provider boundary through
`app/services/retrieval.py`, `app/services/retrieval_semantic_provider.py`, and
`RetrievalStoreService`. The checked-in source-controlled loader defaults to
the deterministic hash fallback for local development, and can build a private
semantic provider only when private runtime settings attest the semantic
backend, approved model, disabled hash fallback, endpoint safety, timeout, and
dimension count. Private endpoints must be configured outside source control
and use HTTPS or a loopback-only local service.

The application also exposes a metadata-only reindex operation at
`POST /api/v1/denial-workflow/sources/reindex-embeddings`. The checked-in route
is admin-only, defaults to dry-run mode, refuses non-dry-run writes with the
development hash provider, and returns only aggregate counts, provider labels,
safe status flags, and blocker/warning tokens. Private production deployments
must inject the approved semantic provider before running a write reindex.

## Safety Boundaries

- Configure semantic backend settings in private runtime configuration only.
- Configure production vector backend settings in private runtime configuration
  only.
- Wire approved semantic embedding adapters through the retrieval provider
  boundary from private runtime code or configuration only.
- Configure `RETRIEVAL_PRIVATE_EMBEDDING_URL`,
  `RETRIEVAL_PRIVATE_EMBEDDING_TOKEN`,
  `RETRIEVAL_PRIVATE_EMBEDDING_DIMENSIONS`, and
  `RETRIEVAL_PRIVATE_EMBEDDING_TIMEOUT_SECONDS` only in private runtime
  configuration when a semantic provider is approved.
- Do not store embedding service URLs, credentials, tokens, raw source text,
  raw document content, vector values, PHI, production claim content, or
  production document content in this repository.
- Keep the hash embedding fallback development-only until semantic backend
  configuration, approved embedding model selection, production vector backend
  configuration, chunk reindexing, vector backend health, and retrieval quality
  smoke checks are complete.
- Keep retrieval source governance, role-scoped access, retention/delete
  controls, audit dashboard checks, encrypted storage checks, and source-text
  redaction checks active before any production promotion.

## Private Operator Steps

1. Select the approved semantic embedding model outside source control.
2. Configure the embedding provider and production vector backend outside source
   control.
3. Render the private runtime environment file with
   `llm-distill/scripts/render_retrieval_vector_private_env.py` only to a
   private path outside source control after semantic backend, approved
   embedding model, production vector backend, hash-fallback disablement,
   reindex, health, quality smoke, rollback, and no-raw-value evidence are
   complete. Confirm command output contains redacted booleans/counts only.
4. Confirm `app/services/retrieval_semantic_provider.py` reports provider-ready
   status using only redacted booleans and blocker codes.
5. Confirm `RetrievalStoreService` is using the approved semantic provider for
   source indexing and query embeddings without logging raw source text or
   vectors.
6. Disable hash fallback for production in private runtime configuration.
7. Run the admin reindex operation in dry-run mode and verify the response
   contains no raw source text, raw vectors, credentials, PHI, secrets, or
   production document content.
8. Reindex active retrieval and corpus chunks with the approved semantic
   embedding model.
9. Confirm stored hash embeddings are absent from active production retrieval
   paths.
10. Run the vector backend health check without logging URLs, credentials,
   source text, vector values, PHI, or production document content.
11. Run a retrieval quality smoke check on approved, non-sensitive fixtures and
   record only boolean status in checked-in evidence.
12. Render the private runtime validation evidence with
   `llm-distill/scripts/render_retrieval_vector_runtime_private_evidence.py`
   only to a private path outside source control after health, quality smoke,
   reindex audit, backup restore, rollback, and no-raw-value attestations are
   complete. Confirm output contains redacted booleans/counts only.
13. Update
   `llm-distill/data/retrieval_vector_backend/vector_backend_evidence.template.json`
   only with booleans, counts, status tokens, and safe blocker identifiers.
14. Rerun `llm-distill/scripts/validate_retrieval_vector_backend.py`.

## Rollback Or Disable Path

- Keep the local hash fallback available for development and non-production
  troubleshooting only.
- If production semantic retrieval health or quality validation fails, disable
  production semantic retrieval in private runtime configuration before serving
  affected workflows.
- Rerun the vector backend validator after any evidence update.
- Do not represent rollback evidence with raw URLs, credentials, source text,
  vector values, PHI, prompts, model responses, claim identifiers, or document
  content.

## Evidence Rules

- Checked-in evidence may include booleans, aggregate counts, status tokens,
  blocker IDs, runbook path, and marker counts only.
- Private rendered environment files must stay outside source control and
  renderer output must be redacted booleans/counts only.
- Private runtime validation evidence files must stay outside source control
  and must not include private evidence references, source text, vector values,
  backend URLs, service labels, credentials, PHI, or production document
  content.
- Checked-in evidence must not include raw embedding vectors, source text,
  document text, backend URLs, service names that expose private infrastructure,
  credentials, approval references, PHI, secrets, production claim content, or
  production document content.
- The report may stay `safe_to_review=true` while
  `vector_backend_ready=false` until semantic backend configuration, production
  vector backend configuration, reindexing, vector backend health, and
  retrieval quality smoke checks are complete.
