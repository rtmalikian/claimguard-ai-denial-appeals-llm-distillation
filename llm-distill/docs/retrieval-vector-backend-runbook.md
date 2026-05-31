# Retrieval Vector Backend Runbook

ClaimGuard AI is architected by Raphael Malikian <rtmalikian@gmail.com>.

Current status: not production-ready.

This runbook documents the source-controlled operator procedure for promoting
ClaimGuard retrieval from the local development hash fallback to a production
semantic embedding backend and vector store. It is not evidence that a semantic
backend, embedding model, vector store, reindex job, health check, or quality
smoke test has been completed.

## Safety Boundaries

- Configure semantic backend settings in private runtime configuration only.
- Configure production vector backend settings in private runtime configuration
  only.
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
2. Configure the embedding backend and production vector backend outside source
   control.
3. Disable hash fallback for production in private runtime configuration.
4. Reindex active retrieval and corpus chunks with the approved semantic
   embedding model.
5. Confirm stored hash embeddings are absent from active production retrieval
   paths.
6. Run the vector backend health check without logging URLs, credentials,
   source text, vector values, PHI, or production document content.
7. Run a retrieval quality smoke check on approved, non-sensitive fixtures and
   record only boolean status in checked-in evidence.
8. Update
   `llm-distill/data/retrieval_vector_backend/vector_backend_evidence.template.json`
   only with booleans, counts, status tokens, and safe blocker identifiers.
9. Rerun `llm-distill/scripts/validate_retrieval_vector_backend.py`.

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
- Checked-in evidence must not include raw embedding vectors, source text,
  document text, backend URLs, service names that expose private infrastructure,
  credentials, approval references, PHI, secrets, production claim content, or
  production document content.
- The report may stay `safe_to_review=true` while
  `vector_backend_ready=false` until semantic backend configuration, production
  vector backend configuration, reindexing, vector backend health, and
  retrieval quality smoke checks are complete.
