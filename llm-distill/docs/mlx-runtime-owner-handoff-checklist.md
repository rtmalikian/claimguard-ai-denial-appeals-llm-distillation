# MLX Runtime Owner Handoff Checklist

ClaimGuard AI is architected by Raphael Malikian <rtmalikian@gmail.com>.

Current status: runtime owner not assigned for production.

This checklist documents the source-controlled owner handoff procedure for the
ClaimGuard MLX student runtime. It is not evidence that an owner has been
assigned, that a private approval reference exists, or that the runtime is
approved for production default routing.

## Required Handoff Gates

- private runtime owner assignment required
- Raphael approval required
- approval reference configured outside source control required
- private launchd copy required
- loopback runtime required
- MLX runtime preflight required
- student status endpoint check required
- student runtime health check required
- supervisor restart test required
- rollback to NVIDIA required

## Conservative Defaults

- Keep `CLAIMGUARD_STUDENT_USE_BY_DEFAULT=false` until all handoff and
  validation gates are complete.
- Keep `CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED=false` until validation evidence
  is ready.
- Keep the private launchd service bound to loopback only.
- Keep rollback to NVIDIA available until Raphael approves removing the
  rollback guard.

## Evidence Rules

- boolean-only evidence
- no approval reference values
- no raw runtime output
- no environment secret values
- no endpoint response bodies
- no model outputs
- no PHI or production document content
- supervisor_ready=false

Record only booleans, counts, timestamps, operator role labels, and blocker
identifiers in checked-in evidence. Store any owner identity, approval
reference, local account path, and deployment path outside source control.
