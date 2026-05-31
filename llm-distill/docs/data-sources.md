# ClaimGuard Source Registry Notes

Use public, synthetic, or formally de-identified data first. Public availability
does not automatically mean training permission.

## Tier 1: Training-Safe Candidates

- Government-authored model notices.
- Agency-authored appeal and adjudication decisions.
- Public decision summaries edited to remove identifying information.
- Synthetic denial and appeal examples generated from public rules/templates.
- Public policy snippets only where reuse terms allow internal training.

## Tier 2: Use After Review

- Legislative hearing exhibits.
- Public comments with appeal-process examples.
- IRO summaries with partial facts.
- State hearing decisions requiring additional PHI screening.
- Public insurer policies with terms-of-use constraints.

## Tier 3: Research-Only Until Cleared

- Court exhibits.
- Actual insurer denial letters from litigation.
- Claim files.
- Patient-submitted public posts.
- Forum or social-media posts.
- Documents containing names, member IDs, claim numbers, addresses, dates of
  birth, provider names tied to rare conditions, or rare-condition narratives.

The machine-readable starter registry is `data/source_registry.json`.
