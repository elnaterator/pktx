# pktx

pktx MCP Server — Python MCP server for resume/personal data, installable via `uvx`.

## Constitution

All project principles, technology constraints, packaging rules, dev workflow, governance defined in [`.specify/memory/constitution.md`](.specify/memory/constitution.md). Authoritative — read before changes.

## Quick Reference

```bash
# Root commands (orchestrates both frontend and backend)
make check      # lint + typecheck + test (both frontend and backend)
make build      # build frontend then backend
make run        # docker compose up --build
make run-local  # build frontend, then run backend locally
make test       # test both frontend and backend
make lint       # lint both frontend and backend
make format     # auto-format both frontend and backend

# Backend-specific (from backend/ directory)
cd backend
make check      # lint + typecheck + test
make test       # uv run pytest
make lint       # ruff check + format check
make run        # uv run pktx (HTTP server)
make format     # auto-format with ruff

# Frontend-specific (from frontend/ directory)
cd frontend
make check      # lint + test
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
    db.py                 # DBConnection protocol
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

**Frontend Organization:** A component used in exactly one page lives in `pages/<name>/`. A component reused across ≥2 pages, or a UI primitive (dialog, form input, badge), lives in `components/`. Types live in `types/` with a barrel `index.ts`. Services are split per resource in `services/api/` with a barrel `index.ts`. Hooks in `hooks/` extract shared state patterns (list loading, detail loading, status messages).

<!-- MANUAL ADDITIONS START -->

## MCP Authentication (OAuth DCR proxy)

`/mcp` is an OAuth2-protected endpoint fronted by FastMCP's `OAuthProxy` (built in
`auth.build_mcp_auth`). The server handles Dynamic Client Registration locally and
proxies authorize/token upstream to one static Clerk OAuth app, so native clients
(Claude Desktop, Cursor, VS Code) register with us — not Clerk — which fixes the
`localhost` vs `127.0.0.1` loopback redirect mismatch. Clients receive proxy-issued
reference JWTs; each `/mcp` call swaps the JWT for the stored Clerk token and
re-validates it (revocation-aware). REST `/api/*` auth is unchanged (Clerk JWT via
`build_get_current_user`). stdio mode uses `PKTX_USER_ID`, no token.

Proxy state (DCR registrations, encrypted upstream tokens, JTI mappings, transient
authorize state) is stored in PostgreSQL via `oauth_store.PostgresKVStore` (table
`oauth_kv`) — **not** a local DiskStore — so it is shared across serverless
instances. Values are Fernet-encrypted at rest, keyed off the Clerk OAuth client
secret. Required env in production: `PKTX_PUBLIC_URL`, `CLERK_ISSUER`,
`CLERK_JWKS_URL`, `CLERK_OAUTH_CLIENT_ID`, `CLERK_OAUTH_CLIENT_SECRET`.

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

### Backend
- Python 3.11+ with type hints + Pydantic validation
- FastMCP >=2.3.0 for MCP server (streamable-http + stdio)
- FastAPI >=0.100.0 for REST API + static file serving
- uvicorn >=0.20.0 for ASGI HTTP server
- PostgreSQL 16+ via `psycopg` + `psycopg-pool`, `DBConnection` protocol, migrations in `migrations.py` (schema v13)
- `uv` for dependency management + packaging
- pytest for testing (unit, contract, integration)
- ruff for linting + formatting
- pyright for type checking
- python-jose, svix (auth logic)

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
- AWS Lambda (container image + Function URL) via Terraform in `infra/`; EventBridge keep-warm rule pings `GET /health` every 5 min (toggle: `keep_warm_enabled` module var)

## Recent Changes
- 017-oauth-dcr-proxy: MCP auth moved to FastMCP `OAuthProxy` (local DCR, loopback-tolerant), proxy state persisted in PostgreSQL (`oauth_kv`, schema v13); new env `CLERK_OAUTH_CLIENT_ID` / `CLERK_OAUTH_CLIENT_SECRET`
- feat-015-tags-handling: Added Python 3.11+ (backend); TypeScript 5.x / React 18 (frontend) + FastAPI ≥0.100.0, FastMCP ≥2.3.0, React 18, Vite 6, Vitest 2 — all existing, no new deps
- feature/002-ci-pipeline: Added Python 3.11 (minimum supported per pyproject.toml) + GitHub Actions, `astral-sh/setup-uv` action
