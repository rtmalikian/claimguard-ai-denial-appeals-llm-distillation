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
4. Reindex active retrieval and corpus chunks with approved semantic
   embeddings.
5. Confirm stored hash embeddings are absent from active production retrieval
   paths.
6. Record reindex job completion as a boolean-only private operational result.
7. Complete a metadata-only reindex audit.
8. Run vector backend health checks without logging values.
9. Run retrieval quality smoke checks on approved non-sensitive fixtures.
10. Update checked-in evidence only with booleans, counts, safe status tokens,
    and blocker identifiers.
