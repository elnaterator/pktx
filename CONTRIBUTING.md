# Contributing to pktx

Thanks for your interest in contributing! This document covers the development workflow,
project conventions, and what to expect when opening a pull request.

## Development setup

Install the required tools (see the [README](README.md#required-tools)): `uv`, Node.js 22+,
Docker, Trivy, and `make`. Terraform and the AWS CLI are only needed for infra work.

```bash
make setup   # uv sync + npm ci
make run     # full app via Docker Compose (app + Postgres)
```

For a faster inner loop, run the pieces directly:

```bash
# Backend (from backend/) — needs a PKTX_DB_URL pointing at Postgres
cd backend && make run        # uv run pktx (HTTP server on :8000)

# Frontend (from frontend/) — Vite dev server with HMR, proxies /api to :8000
cd frontend && make run
```

Copy `.env.example` to `.env` and fill in the Clerk values (a free Clerk account works).

## Checks and tests

All of these must pass before a PR is merged (CI runs them too):

```bash
make check      # everything: lint + typecheck + audit + test + IaC scan
make format     # auto-format (ruff + prettier-style ESLint fixes)
```

Backend tests use [testcontainers](https://testcontainers.com/) to spin up a real
PostgreSQL, so Docker must be running. Test layout:

- `backend/tests/unit/` — service and model logic
- `backend/tests/contract/` — REST + MCP API contracts
- `backend/tests/integration/` — end-to-end flows across interfaces
- `frontend/src/__tests__/` — Vitest + React Testing Library component tests

New behavior needs tests at the appropriate layer; bug fixes need a regression test.

## Security checks

`make check` fails on any of these:

- **ruff `S` (bandit) rules**: Python security lint. Suppress a false positive with
  `# noqa: S<code> — <why it is safe>`. A bare `noqa` is not accepted in review.
- **`pip-audit`** (`make -C backend audit`): known CVEs in the locked runtime deps.
- **`npm audit --audit-level=high --omit=dev`** (`make -C frontend audit`).
- **Trivy IaC** (`make tf-check`): HIGH/CRITICAL Terraform misconfigurations.

CI's `Security` workflow also scans the built image and the repo for secrets with Trivy,
on every PR and weekly. CodeQL runs through GitHub's default setup.

**Waivers** (only when no fix exists, or the finding doesn't apply):

| Scanner | Where | Format |
|---|---|---|
| pip-audit | `PIP_AUDIT_IGNORE` in `backend/Makefile` | ID + reason + expiry comment |
| Trivy image / secret | `.trivyignore` | ID + `exp:YYYY-MM-DD` + reason comment |
| Trivy IaC | inline `#trivy:ignore:<ID> <reason>` above the attribute | |

Dependency updates come from Renovate (`renovate.json`): weekly grouped PRs, and
security fixes immediately. Patch and dev-dependency updates auto-merge once CI passes;
minor and major updates wait for a human.

## Project conventions

- **Read [AGENTS.md](AGENTS.md)** for the project layout and
  [.specify/memory/constitution.md](.specify/memory/constitution.md) for the project
  principles — both are authoritative.
- **Python**: 3.11+, full type hints, Pydantic models, `ruff` formatting, `pyright` clean.
- **TypeScript**: strict mode, CSS Modules for styling, components used by one page live in
  `pages/<name>/`, shared components in `components/`.
- **Business logic lives in `*_service.py`**, shared by both the REST routes and MCP tools —
  never duplicate logic between the two interfaces.
- **Database changes** go through the migration framework in `backend/src/pktx/migrations.py`
  (one schema version bump per change).

## Branches and commits

- Branch from `main`: `<type>/<short-slug>` where `<type>` is one of
  `feat`, `fix`, `chore`, `docs`, `refactor`, `perf`, `test`, `build`, `ci`.
- Use [Conventional Commits](https://www.conventionalcommits.org/):
  `feat(scope): subject`, `fix: subject`, etc. Subject ≤ 72 chars, imperative mood.
- Keep commits atomic — one logical change per commit.

## Pull requests

- Keep PRs focused; unrelated refactors go in separate PRs.
- Describe **what** changed and **why**; link the issue or roadmap item if one exists.
- `make check` must be green.
- PRs touching `infra/` should include `terraform fmt` output and note any resources that
  will be replaced on apply.

## Reporting issues

Open a GitHub issue with reproduction steps, expected vs. actual behavior, and relevant
logs. Security issues: please report privately to the maintainer rather than opening a
public issue.
