# ClaimGuard Dependency Security Runbook

ClaimGuard AI is architected by Raphael Malikian <rtmalikian@gmail.com>.

Current status: dependency_security_ready=false.

This runbook defines source-controlled dependency security governance for
ClaimGuard without storing vulnerability database output, private scan reports,
approval references, package repository credentials, PHI, secrets, production
documents, or raw production data in the repository.

## Scope

Dependency security evidence must cover:

- Python dependencies from `requirements.txt` and `pyproject.toml`.
- Frontend dependencies from `frontend/package.json` and
  `frontend/package-lock.json`.
- Production backend and frontend container images.
- Dependency lockfiles and production Docker build inputs.

The runbook does not certify production readiness by itself. Production
readiness stays blocked until private scan evidence, remediation evidence,
risk acceptance, rebuild/retest evidence, and metadata-only audit review are
complete.

## Required Private Evidence

Store the following outside source control:

- Python dependency scan reference.
- Frontend dependency scan reference.
- Container image scan reference.
- Dependency remediation or risk-acceptance reference.
- Private aggregate dependency security summary.

The final private evidence renderer reads only environment-variable names and
private summary counts. Do not store approval reference values, raw vulnerability
details, scanner output, package repository credentials, SBOM file paths,
container registry URLs, PHI, secrets, or production document content in source
control.

## Minimum Scan Requirements

Before production approval:

1. Run a Python dependency scan using an approved tool such as `pip-audit`,
   `safety`, or an equivalent private scanner.
2. Run a frontend dependency scan using an approved tool such as `npm audit` or
   an equivalent private scanner.
3. Run a production container image scan using an approved tool such as
   `trivy`, `grype`, or an equivalent private scanner.
4. Review lockfiles and production Docker build inputs.
5. Remediate or privately approve every critical/high finding before
   production use.
6. Document compensating controls for any accepted finding outside source
   control.
7. Rebuild and retest after remediation.
8. Keep private scan reports and approval references outside source control.

## Metadata-Only Reporting

Checked-in evidence may contain only:

- Boolean scan-completion flags.
- Aggregate package, image, and remediated-or-approved finding counts.
- Generic blocker codes.
- Environment-variable names for private references.
- `dependency_security_ready=false` until every private gate is complete.

Checked-in evidence must not contain:

- raw vulnerability details, raw vulnerability names, CVE details, CVSS vectors, proof-of-concept text, or
  scanner output.
- Private dependency scan paths or approval reference values.
- Package registry credentials, container registry URLs, tokens, API keys, or
  passwords.
- PHI, production claim data, uploaded documents, EDI payloads, prompts, or
  model responses.

## Validation Commands

Run from the repository root:

```bash
python3 llm-distill/scripts/validate_dependency_security_evidence.py
python3 llm-distill/scripts/run_phi_plan_production_readiness_audit.py
```

The PHIplan production-readiness audit must be rerun after dependency security
evidence is approved.

## Private Renderer

Use `llm-distill/scripts/render_dependency_security_private_evidence.py` only
for private output paths outside source control. Approved mode must refuse to
write if private scan references are missing, the private aggregate dependency
security summary is missing or incomplete, raw values are marked as included,
or dependency security evidence is not ready.
