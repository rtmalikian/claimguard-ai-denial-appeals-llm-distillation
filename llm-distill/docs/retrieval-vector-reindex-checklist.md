# Retrieval Vector Reindex Checklist

ClaimGuard AI is architected by Raphael Malikian <rtmalikian@gmail.com>.

Current status: not reindexed for production.

This checklist documents the source-controlled review steps that must be
completed before retrieval chunks can be represented as production semantic
vector evidence. It is not evidence that a production semantic backend, vector
store, reindex job, health check, or retrieval quality smoke check has been
completed.

## Required Preconditions

- approved semantic embedding model required before reindexing active chunks.
- production vector backend required in private runtime configuration.
- hash fallback disabled for production required before production promotion.
- application reindex operation available before private semantic providers are
  allowed to update encrypted chunk metadata.
- active retrieval chunks reindexed required with the approved semantic model.
- stored hash embeddings absent required from active production retrieval paths.
- reindex job completion required before toggling evidence booleans.
- reindex audit required before production retrieval can be treated as ready.
- vector backend health check required after private runtime configuration.
- retrieval quality smoke check required on approved non-sensitive fixtures.

## Evidence Rules

- boolean-only evidence must be used in checked-in templates and reports.
- no raw source text, raw document content, vector values, backend URLs,
  credentials, approval references, PHI, secrets, production claim content, or
  production document content may be checked in.
- `vector_backend_ready=false` remains the expected checked-in state until all
  private runtime configuration, reindex, audit, health, and smoke-check steps
  pass.

## Operator Checklist

1. Confirm the approved semantic embedding model outside source control.
2. Configure the production vector backend outside source control.
3. Disable production hash fallback outside source control.
4. Confirm the metadata-only application reindex operation is available and
   dry-run results show no raw text, vectors, credentials, PHI, or secrets.
5. Reindex active retrieval and corpus chunks with approved semantic
   embeddings.
6. Confirm stored hash embeddings are absent from active production retrieval
   paths.
7. Record reindex job completion as a boolean-only private operational result.
8. Complete a metadata-only reindex audit.
9. Run vector backend health checks without logging values.
10. Run retrieval quality smoke checks on approved non-sensitive fixtures.
11. Update checked-in evidence only with booleans, counts, safe status tokens,
    and blocker identifiers.
