# Production Corpus Pair Source Checklist

ClaimGuard AI is architected by Raphael Malikian <rtmalikian@gmail.com>.

Current status: approved non-synthetic pair not complete for production.

This checklist documents the source-controlled pair and source review procedure
for production denial/appeal training candidates. It is not evidence that a
real document pair has been approved, that source documents have been reviewed,
or that production corpus training is ready.

## Required Pair And Source Gates

- approved non-synthetic denial/appeal pair required
- denial letter role required
- appeal letter role required
- shared pair id required
- pair ids reviewed outside source control required
- source documents reviewed outside source control required
- privacy review required
- license review required
- residual-risk review required
- training scope review required
- no-PHI review required
- source license scope documented required

## Evidence Rules

- boolean-only evidence
- no raw denial letters
- no raw appeal letters
- no source paths
- no source URLs
- no checksums
- no approval reference values
- no PHI
- production_corpus_ready=false

Record only booleans, counts, blocker identifiers, source-type categories,
document-role categories, and aggregate pair counts in checked-in evidence.
Store raw documents, source locations, checksums, approval references, reviewer
identities, and production review records outside source control.
