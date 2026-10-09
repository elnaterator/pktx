# pktx

pktx MCP Server — Python MCP server for resume/personal data, installable via `uvx`.

## Constitution

All project principles, technology constraints, packaging rules, dev workflow, governance defined in [`.specify/memory/constitution.md`](.specify/memory/constitution.md). Authoritative — read before changes.

## Quick Reference

```bash
# Root commands (orchestrates both frontend and backend)
make check      # lint + typecheck + audit + test + Trivy IaC (frontend, backend, infra)
make build      # build frontend then backend
make run        # docker compose up --build
make run-local  # build frontend, then run backend locally
make test       # test both frontend and backend
make lint       # lint both frontend and backend
make format     # auto-format both frontend and backend

# Backend-specific (from backend/ directory)
cd backend
make check      # lint + typecheck + pip-audit + test
make test       # uv run pytest
make lint       # ruff check + format check
make run        # uv run pktx (HTTP server)
make format     # auto-format with ruff

# Frontend-specific (from frontend/ directory)
cd frontend
make check      # lint + npm audit + test
make build      # npm run build (Vite production build)
make run        # npm run dev (Vite dev server with HMR)
make lint       # npm run lint (ESLint)
make test       # npm run test (Vitest)
```

## Project Layout

```
frontend/                 # React SPA
  src/
    pages/                # Route-level page modules
      home/               # HomeView
      resumes/            # ListView, DetailView, ResumeView, *Section components
      applications/       # ListView, DetailView
      accomplishments/    # ListView, DetailView
      notes/              # ListView, DetailView
      contacts/           # ListView, DetailView
    components/           # Shared components (used across ≥2 pages)
    hooks/                # Reusable state hooks (useResourceList, useResourceDetail, etc.)
    services/
      api/                # Per-resource API modules + shared client
        client.ts         # fetch wrapper, auth, error handling
        index.ts          # barrel export
    types/                # Per-resource type definitions + barrel index.ts
    __tests__/            # Vitest component tests
    App.tsx               # Root component
    main.tsx              # Entry point
    router.tsx            # Route definitions
    index.css             # Global styles
  public/                 # Static assets
  dist/                   # Build output (served by backend)
  index.html              # HTML template
  package.json            # Node.js dependencies
  tsconfig.json           # TypeScript config
  vite.config.ts          # Vite build + proxy config
  eslint.config.js        # ESLint config
  Makefile                # Frontend build targets
backend/                  # Python FastAPI + MCP server
  src/pktx/               # Python package
    server.py             # FastAPI + MCP server entrypoint
    models.py             # Pydantic data models
    config.py             # Configuration (env-var resolvers)
    database.py           # PostgreSQL operations (psycopg + pool)
    migrations.py         # Schema migration framework (schema_version table)
    db.py                 # DBConnection protocol + per-request RequestConnection
    validation.py         # Shared input validation (tags, http(s) URLs, lengths)
    auth.py               # Clerk JWT (REST) + MCP OAuth proxy (build_mcp_auth)
    oauth_store.py        # PostgreSQL-backed AsyncKeyValue for OAuth-proxy state
    resume_service.py     # Shared business logic (one *_service.py per resource)
    export_service.py     # Per-user JSON export behind GET /api/export
    api/                  # REST API routes
      routes.py           # FastAPI route handlers
    tools/                # MCP tool handlers (one *_tools.py per resource)
  tests/
    unit/                 # Unit tests
    contract/             # MCP + REST API contract tests
    integration/          # Integration tests (incl. cross-interface, static serving)
  pyproject.toml          # Python package config
  uv.lock                 # Locked dependencies
  Makefile                # Backend build targets
Makefile                  # Root orchestrator
Dockerfile                # Multi-stage Docker build (Node.js + Python)
docker-compose.yml        # Docker Compose configuration
specs/                    # Feature specifications
.specify/                 # Spec-kit configuration
.github/                  # GitHub Actions CI
```

**Connect UX (030):** per-assistant connect steps, snippets, install links, and `lastVerified` dates live only in `frontend/src/components/connect/connectAssistants.ts` — edit data there, not JSX. Shared by the side panel (`ConnectAssistantPanel`) and `/connect` (`pages/connect`).

**Frontend Organization:** A component used in exactly one page lives in `pages/<name>/`. A component reused across ≥2 pages, or a UI primitive (dialog, form input, badge), lives in `components/`. Types live in `types/` with a barrel `index.ts`. Services are split per resource in `services/api/` with a barrel `index.ts`. Hooks in `hooks/` extract shared state patterns (list loading, detail loading, status messages).

<!-- MANUAL ADDITIONS START -->

## MCP Authentication (OAuth proxy: CIMD + DCR)

`/mcp` is an OAuth2-protected endpoint fronted by FastMCP's `OAuthProxy` (built in
`auth.build_mcp_auth`). Clients identify themselves to us, not to Clerk, and we proxy
authorize/token upstream to one static Clerk OAuth app — which fixes the `localhost`
vs `127.0.0.1` loopback redirect mismatch for native clients (Claude Desktop, Cursor,
VS Code). Both MCP 2025-11-25 mechanisms work: Client ID Metadata Documents
(`enable_cimd=True`, advertised as `client_id_metadata_document_supported`) and
Dynamic Client Registration at `/register`.

Clients receive proxy-issued reference JWTs bound to `aud=<PKTX_PUBLIC_URL>/mcp`;
each `/mcp` call validates that audience, then swaps the JWT for the stored Clerk
token and re-validates it (revocation-aware). The upstream Clerk token's own audience
is Clerk's client id and is not checked — there we are the OAuth client, not the
resource. RFC 9728 metadata is served at `/.well-known/oauth-protected-resource/mcp`
and aliased at the root path (`server._add_root_resource_metadata_alias`). Redirect
URIs are restricted to loopback plus whatever `PKTX_EXTRA_CLIENT_REDIRECT_URIS` adds
(for hosted clients). REST `/api/*` auth is a Clerk session JWT via
`build_get_current_user`: signature + issuer + `azp` must be in
`CLERK_AUTHORIZED_PARTIES` (default: origin of `PKTX_PUBLIC_URL`). stdio mode uses
`PKTX_USER_ID` (required there, ignored over HTTP), no token.

Proxy state (DCR registrations, encrypted upstream tokens, JTI mappings, transient
authorize state) is stored in PostgreSQL via `oauth_store.PostgresKVStore` (table
`oauth_kv`) — **not** a local DiskStore — so it is shared across serverless
instances. Values are Fernet-encrypted at rest, keyed off the Clerk OAuth client
secret. Required env in production: `PKTX_PUBLIC_URL`, `CLERK_ISSUER`,
`CLERK_JWKS_URL`, `CLERK_OAUTH_CLIENT_ID`, `CLERK_OAUTH_CLIENT_SECRET`. Optional:
`PKTX_EXTRA_CLIENT_REDIRECT_URIS`, `CLERK_AUTHORIZED_PARTIES`.

## Data Access Rules (027)

- **Per-request connection.** Services are built once with a `db.RequestConnection`;
  it lazily checks a pooled connection out per HTTP request (`DBSessionMiddleware`)
  or per stdio tool call. One transaction per scope: commit on success, rollback on
  exception / 5xx / MCP tool error. Never hold a raw connection globally.
- **Fail-closed user scoping.** Every `database.py` function and service method takes
  a required `user_id: str`; ownership is enforced in SQL (`WHERE id = %s AND
  user_id = %s`) and a miss is 404 (no 403 existence oracle). No-auth test mode runs
  as `"legacy"`. `tests/integration/test_route_scoping.py` calls every route as
  another user and fails on any route it does not know — register new routes there.
- **Validate at the service boundary** with `pktx.validation` (`normalize_tags`,
  `validate_http_url` — http(s) only, bare hosts get `https://`, `check_len`).
  Frontend renders user URLs only through `components/ExternalLink`.
- Multi-step writes use `conn.transaction()`, never manual `SAVEPOINT`.

<!-- MANUAL ADDITIONS END -->

## Active Technologies
- Python 3.11+ (backend); TypeScript 5.x / React 18 (frontend) + FastAPI ≥0.100.0, FastMCP ≥2.3.0, `@clerk/clerk-react` v5+, `python-jose[cryptography]`, `svix` (008-authentication)
- SQLite (schema v3 → v4); `users` table added as FK anchor for `resume_version`, `application`, `accomplishment` (008-authentication)
- Python 3.11+ (backend); TypeScript 5.x / React 18 (frontend) + FastAPI ≥0.100.0, FastMCP ≥2.3.0, psycopg[binary] ≥3.1, psycopg-pool ≥3.1, testcontainers[postgres] ≥4.0 (dev) (009-postgres)
- PostgreSQL 16+ (009-postgres)
- HCL (Terraform 1.7+) + `hashicorp/aws` provider ~5.x, `hashicorp/terraform` 1.7+ (010-aws-infra)
- Remote state in S3 + DynamoDB (bootstrapped manually); app uses Neon PostgreSQL (connection config via SSM) (010-aws-infra)
- Python 3.11+ (backend); TypeScript 5.x / React 18 (frontend) + FastAPI ≥0.100.0, FastMCP ≥2.3.0, `clerk-backend-api ≥1.0.0` (new — Python SDK for dual auth), `@clerk/clerk-react` v5+ (existing), `python-jose[cryptography]` (existing — retained for REST API JWT path) (011-mcp-instructions)
- PostgreSQL 16+ (no schema changes) (011-mcp-instructions)
- TypeScript 5.6 / React 18 + React Router v7 (new), `@clerk/clerk-react` v5 (existing) (012-client-side-routing)
- N/A (no storage changes) (012-client-side-routing)
- Python 3.11+ (backend), TypeScript 5.x (frontend) + FastMCP >=2.3.0, FastAPI >=0.100.0, React 18, Vite 6 (all existing — no new deps) (013-personal-context-section)
- PostgreSQL 16+, schema v5 → v6 migration (013-personal-context-section)
- TypeScript 5.x / React 18 + React Router v7, Vite 6, CSS Modules, `@clerk/clerk-react` v5, `lucide-react` (new — icon library) (014-ux-overhaul)
- N/A — no storage changes (014-ux-overhaul)
- Python 3.11+ (backend); TypeScript 5.x / React 18 (frontend) + FastAPI ≥0.100.0, FastMCP ≥2.3.0 (backend); React 18, Vite 6, Vitest 2 (frontend) — all existing, no new deps (feat-015-tags-handling)
- PostgreSQL 16+ — no schema changes (feat-015-tags-handling)
- Python 3.11+ (backend) + FastMCP ≥2.14.5 `OAuthProxy` (existing dep), `py-key-value-aio` + `cryptography` (transitive via FastMCP) — no new direct deps (017-oauth-dcr-proxy)
- PostgreSQL 16+, schema v12 → v13 (`oauth_kv` table for OAuth-proxy state) (017-oauth-dcr-proxy)
- Python 3.11+ (backend) + FastMCP ≥3.4.7 (major upgrade from 2.x; brings CIMD + audience-bound proxy tokens) — no new direct deps (025-mcp-auth-spec-gaps)
- PostgreSQL 16+ — no schema changes (025-mcp-auth-spec-gaps)

### Backend
- Python 3.11+ with type hints + Pydantic validation
- FastMCP >=3.4.7 for MCP server (streamable-http + stdio)
- FastAPI >=0.100.0 for REST API + static file serving
- uvicorn >=0.20.0 for ASGI HTTP server
- PostgreSQL 16+ via `psycopg` + `psycopg-pool`, `DBConnection` protocol, migrations in `migrations.py` (schema v14)
- `uv` for dependency management + packaging
- pytest for testing (unit, contract, integration)
- ruff for linting + formatting
- pyright for type checking
- PyJWT[crypto], svix (auth logic)

### Frontend
- React 18 + TypeScript 5.x
- Vite 6 for build + dev server
- Clerk (Auth SDK)
- Vitest 2 + React Testing Library for component tests
- ESLint 9 + typescript-eslint for linting
- CSS Modules for component styling

### Infrastructure
- Docker + Docker Compose for containerized deployment (multi-stage build)
- GNU Make for build orchestration (root + per-directory Makefiles)
- Security: ruff `S` (bandit), `pip-audit`, `npm audit`, Trivy (IaC in `make check`; image + secrets in `security.yml`), CodeQL default setup, Renovate (`renovate.json`). Waivers: `PIP_AUDIT_IGNORE` (backend/Makefile), `.trivyignore`, inline `#trivy:ignore:<ID>`
- AWS Lambda (container image + Function URL) via Terraform in `infra/`; EventBridge keep-warm rule pings `GET /health` every 5 min (toggle: `keep_warm_enabled` module var)

## Recent Changes
- 029-pyjwt: python-jose → PyJWT for REST Clerk JWT verification (drops `ecdsa`/`rsa`/`pyasn1` and the PYSEC-2026-1325 pip-audit waiver); RS256 pinned, unusable JWKS entries → 401
- 028-security-scanning: Renovate + Trivy (replaces Checkov) + pip-audit + npm audit + ruff `S`; new `security.yml` (PR + weekly); Dockerfile on node 22, all images digest-pinned, runtime drops system pip/setuptools and applies Debian security updates; Actions SHA-pinned with read-only `permissions`; vulnerable deps bumped; unused `clerk-backend-api` dropped
- 027-security-fixes: fail-closed user scoping (required `user_id`, owner checks in SQL, 404 not 403), legacy `/api/resume*` routes removed, per-request pooled connection + transaction, http(s)-only URLs (server + `ExternalLink`), tag/length validation, REST JWT `azp` check (new optional env `CLERK_AUTHORIZED_PARTIES`), `PKTX_USER_ID` stdio-only, JWKS refetch throttle, 1 MB body cap; schema v13 → v14 (data repair)
- 025-mcp-auth-spec-gaps: FastMCP 2.14.5 → 3.4.7; MCP 2025-11-25 gaps closed — CIMD client ids (`enable_cimd`), proxy tokens audience-bound to `<public>/mcp`, root `/.well-known/oauth-protected-resource` alias; new optional env `PKTX_EXTRA_CLIENT_REDIRECT_URIS`
- 017-oauth-dcr-proxy: MCP auth moved to FastMCP `OAuthProxy` (local DCR, loopback-tolerant), proxy state persisted in PostgreSQL (`oauth_kv`, schema v13); new env `CLERK_OAUTH_CLIENT_ID` / `CLERK_OAUTH_CLIENT_SECRET`
- feat-015-tags-handling: Added Python 3.11+ (backend); TypeScript 5.x / React 18 (frontend) + FastAPI ≥0.100.0, FastMCP ≥2.3.0, React 18, Vite 6, Vitest 2 — all existing, no new deps
- feature/002-ci-pipeline: Added Python 3.11 (minimum supported per pyproject.toml) + GitHub Actions, `astral-sh/setup-uv` action
