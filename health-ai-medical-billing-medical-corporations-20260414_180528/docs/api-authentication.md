# ClaimGuard API Authentication And Authorization

ClaimGuard AI is architected by Raphael Malikian <rtmalikian@gmail.com>.

Current Objective Scratchpad: Document the current API authentication and role
requirements without adding secrets, production data, PHI, or filing-ready
workflow claims.

## Scope

This document describes the current FastAPI authentication and role behavior in
`app/main.py`, `app/middleware/auth.py`, `app/core/auth.py`, and the routers
under `app/api/v1/`. It is operational documentation only; it does not change
runtime configuration or approve production use.

## Public Routes

The following routes are reachable without a bearer token:

| Route | Purpose |
|---|---|
| `GET /` | API root metadata |
| `GET /health` | Service health checks |
| `GET /docs` | Swagger UI |
| `GET /docs/oauth2-redirect` | Swagger OAuth redirect helper |
| `GET /redoc` | ReDoc UI |
| `GET /openapi.json` | OpenAPI schema |
| `GET /favicon.ico` | Browser icon fallback |
| `POST /api/v1/auth/login` | JWT login |

All other `/api/v1/*` routes require `Authorization: Bearer <access_token>`.
Non-API routes outside `/api/v1` pass through the JWT middleware without token
enforcement.

## Token Flow

1. A configured active user signs in through `POST /api/v1/auth/login`.
2. The response returns a JWT access token, token type, expiry seconds, and safe
   user metadata.
3. API clients send the token on protected routes with:

```bash
Authorization: Bearer "$CLAIMGUARD_TOKEN"
```

Tokens are created by `app/core/security.py` and currently include `sub`,
`email`, `full_name`, and `role` claims. The expiry is controlled by
`ACCESS_TOKEN_EXPIRE_MINUTES`.

Operational rules:

- Use HTTPS or trusted local networking for any non-local deployment.
- Do not put bearer tokens in query strings, logs, screenshots, changelog
  entries, support tickets, or frontend bundles.
- Do not commit real bootstrap credentials, generated tokens, API keys, or
  private `.env` files.
- Rotate `SECRET_KEY` and user credentials through a controlled environment
  process; do not hardcode replacements in source files.

## Roles

The current role constants live in `app/core/auth.py`.

| Role | Intended use |
|---|---|
| `admin` | Administrative users who can view protected audit dashboards and metrics |
| `billing_staff` | Billing users who can create, update, upload, analyze, and generate draft work products |
| `viewer` | Read-only users for non-admin read endpoints |

Route dependencies use these role groups:

| Group | Roles |
|---|---|
| `READ_ROLES` | `admin`, `billing_staff`, `viewer` |
| `WRITE_ROLES` | `admin`, `billing_staff` |
| `ADMIN_ROLES` | `admin` |

## Authorization Matrix

| Route family | Required role group | Notes |
|---|---|---|
| `GET /api/v1/auth/me`, `POST /api/v1/auth/logout` | Any authenticated active user | User state is rechecked through `get_current_user` and database lookup for `/me`. |
| Claim prediction, claim submission, document analysis, document upload, batch EDI upload, and document retirement | `WRITE_ROLES` | Upload routes also use metadata-only document-surface inspection and safe audit details. |
| Claim list/detail, claim document read, claim-document governance summary | `READ_ROLES` | Patient-search filters still enforce minimum identifier safety in the route code. |
| Claim-document audit dashboard | `ADMIN_ROLES` | Returns safe audit metadata, not raw uploaded document content. |
| Analytics trends, analytics summary, prediction accuracy | `READ_ROLES` | Prediction accuracy returns aggregate metrics only. |
| Appeal generation | `WRITE_ROLES` | Draft output is for human review and is not filing-ready. |
| Patient create/update | `WRITE_ROLES` | Patient read/list routes use `READ_ROLES`. |
| Patient delete | `ADMIN_ROLES` | Destructive patient action is admin-only. |
| Denial workflow analysis, corpus validation/de-identification/review/import, retrieval source create/list/search/delete, export, source registry, student status, model-improvement status | `WRITE_ROLES` | Workflow and corpus routes use metadata-only review gates where applicable. |
| Retrieval-source audit dashboard | `ADMIN_ROLES` | Audit route returns safe metadata only. |
| Prometheus metrics | `ADMIN_ROLES` | Emits aggregate counts and boolean runtime flags only. |

## Safe Login Example

Use synthetic or local test credentials from a private `.env` file only:

```bash
curl -sS -X POST "http://localhost:8001/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${BOOTSTRAP_ADMIN_EMAIL}\",\"password\":\"${BOOTSTRAP_ADMIN_PASSWORD}\"}"
```

After extracting the token into `CLAIMGUARD_TOKEN`, call a protected route:

```bash
curl -sS "http://localhost:8001/api/v1/analytics/summary" \
  -H "Authorization: Bearer ${CLAIMGUARD_TOKEN}"
```

## Failure Shape

Missing, invalid, expired, or malformed bearer tokens return structured JSON
errors with a `WWW-Authenticate: Bearer` header. The auth middleware does not
include raw headers, token values, request bodies, PHI, credentials, or
production document content in the error payload.

