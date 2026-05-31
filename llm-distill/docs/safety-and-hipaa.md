# Safety and HIPAA Controls

Treat uploaded denial letters, EOBs, medical records, payer portal notices, and
claim files as PHI by default.

## Required Controls

- No user-uploaded PHI in training by default.
- Explicit opt-in before user data is used for improvement.
- Automated PHI scan plus human privacy review before any real user document is
  allowed into a dataset.
- Minimum necessary PHI in appeal packets.
- Encryption at rest and in transit for production document storage.
- Role-based access controls and per-document audit logs.
- BAA-backed vendors only if PHI is sent outside the local environment.

## Model Behavior Rules

The model must not fabricate deadlines, citations, plan language, payer
addresses, clinical facts, legal conclusions, or coverage guarantees. It must
mark unsupported facts as missing, cite retrieved sources for procedural
recommendations, and keep appeal drafts in `draft_for_human_review` status.

## Training Data Rule

Use public, synthetic, or formally de-identified data. Do not train on raw user
uploads.
