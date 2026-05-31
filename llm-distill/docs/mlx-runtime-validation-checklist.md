# MLX Runtime Validation Checklist

ClaimGuard AI is architected by Raphael Malikian <rtmalikian@gmail.com>.

Current status: not runtime-validated.

This checklist documents the source-controlled validation sequence for the
ClaimGuard MLX student runtime supervisor. It is not evidence that the private
launchd service has been installed, loaded, health checked, restarted, or
approved for production default routing.

## Safety Boundaries

- Keep `CLAIMGUARD_STUDENT_USE_BY_DEFAULT=false` until Raphael approval,
  approval-reference configuration, supervised runtime evidence, health checks,
  and rollback review are complete.
- Keep `CLAIMGUARD_RUNTIME_PROFILE=student_denial_workflow_local_only`.
- Keep the MLX server bound to loopback only.
- Do not store approval reference values, local account paths, command output,
  environment values, endpoint responses, model outputs, PHI, secrets,
  production claim content, or production document content in source control.
- Checked-in validation evidence must be boolean-only evidence with status
  tokens, blocker identifiers, aggregate counts, and no raw runtime output.

## Required Validation Steps

1. Private launchd plist render required outside source control before loading
   the private launchd service.
2. MLX runtime preflight required before loading the private launchd service.
3. Private launchd user session load required before auto-launch readiness.
4. Student status endpoint check required after the runtime starts.
5. Student runtime health check required before any default routing request.
6. Supervisor restart test required before production auto-launch readiness.
7. Rollback to NVIDIA required if any validation step fails.
8. Private supervisor evidence render required outside source control after all
   validation booleans pass.

## Evidence Rules

- Record only booleans for `mlx_runtime_preflight_ready`,
  `student_status_endpoint_checked`, `student_runtime_health_ok`,
  `supervisor_loaded_in_user_session`, and `supervisor_restart_test_passed`.
- Render final private evidence with
  `llm-distill/scripts/render_mlx_runtime_supervisor_private_evidence.py` only
  to a private path, and verify the summary contains redacted booleans/counts
  only.
- Do not paste logs, shell output, local usernames, private paths, endpoint
  response bodies, prompts, model responses, approval references, PHI, secrets,
  credentials, production claim content, or production document content.
- The supervisor report may stay `safe_to_review=true` while
  `supervisor_ready=false` until private owner assignment, runtime preflight,
  status endpoint check, runtime health, launchd load evidence, and restart
  validation are complete.
