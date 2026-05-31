# MLX Runtime Supervisor Runbook

ClaimGuard AI is architected by Raphael Malikian <rtmalikian@gmail.com>.

This runbook documents the source-controlled operator procedure for the local
MLX student runtime supervisor. It is not evidence that the supervisor has been
installed, loaded, health checked, or approved for production default routing.

## Safety Boundaries

- Use a private operator copy of
  `llm-distill/data/runtime_supervision/claimguard.mlx-student.launchd.template.plist`.
- Replace `/ABSOLUTE/PATH/TO` only in the private copy outside source control.
- Keep the launchd service bound to loopback only.
- Keep `CLAIMGUARD_RUNTIME_PROFILE=student_denial_workflow_local_only`.
- Do not store approval reference values, environment secrets, model endpoint
  credentials, PHI, production claim content, or production document content in
  this repository, in launchd environment variables, or in checked-in evidence.
- Keep `CLAIMGUARD_STUDENT_USE_BY_DEFAULT=false` until Raphael approval,
  non-secret approval-reference configuration, runtime owner assignment,
  supervisor validation, and rollback review are complete.

## Private Operator Steps

1. Render a private launchd plist with
   `llm-distill/scripts/render_mlx_launchd_private_copy.py`; write the output
   outside this repository.
2. Confirm the renderer refuses source-control output paths and reports only
   redacted booleans/counts.
3. Replace placeholder paths only through the rendered private copy outside
   source control.
4. Confirm the private plist still runs `mlx_lm.server` directly, uses
   `--adapter-path`, binds to `127.0.0.1`, keeps `KeepAlive` enabled, and has
   stdout/stderr log paths outside this repository.
5. Run the MLX runtime preflight and confirm the accepted adapter path resolves
   before loading launchd.
6. Load the private plist in the user launchd session only after private
   operator ownership is assigned.
7. Check the local MLX server health and the ClaimGuard student status endpoint.
8. Perform a supervised restart test and record only boolean evidence in
   `llm-distill/data/runtime_supervision/supervisor_evidence.template.json`.

## Rollback To NVIDIA

- Unload the private launchd job from the user session.
- Keep default routing on NVIDIA by leaving
  `CLAIMGUARD_STUDENT_USE_BY_DEFAULT=false`.
- Use the rollback-to-NVIDIA path before any production default-student cutover
  if health checks, restart checks, or approval gates fail.
- Rerun `llm-distill/scripts/validate_mlx_runtime_supervisor.py` after any
  evidence update.

## Evidence Rules

- The checked-in evidence file may record booleans, counts, marker status, and
  blocker identifiers only.
- Do not paste command output that contains local account names, approval
  references, environment values, raw prompts, model responses, or document
  content.
- The report may stay `safe_to_review=true` while `supervisor_ready=false` until
  private owner assignment, runtime preflight, health checks, launchd load
  evidence, and restart validation are all complete.
