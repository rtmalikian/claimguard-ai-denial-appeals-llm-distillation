# Production Corpus Collection License Checklist

ClaimGuard AI is architected by Raphael Malikian <rtmalikian@gmail.com>.

Current status: corpus collection and licensing review not complete for production.

This checklist documents the source-controlled collection and licensing review
procedure for production denial/appeal training candidates. It is not evidence
that any source collection has been approved, that source terms have been
accepted, or that production corpus training is ready.

## Required Collection And License Gates

- source inventory required
- source category documented required
- license terms reviewed outside source control required
- terms-of-use review required
- payer policy reuse restrictions reviewed required
- public source scope documented required
- real de-identified source scope documented required
- collection owner documented outside source control required
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

Record only booleans, counts, source-type categories, document-role
categories, license-status categories, and aggregate coverage counts in
checked-in evidence. Store raw documents, source locations, source licenses,
terms text, approval references, reviewer identities, and production collection
records outside source control.
