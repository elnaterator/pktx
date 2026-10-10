# pktx

**pktx** ("personal context") is a self-hostable server for your professional data — resumes,
job applications, accomplishments, notes, and contacts — with a web UI and an
[MCP](https://modelcontextprotocol.io) interface so AI assistants can work with that data
directly.

Track accomplishments as they happen; let your assistant pull them when tailoring a resume
or drafting a cover letter.

## Features

- **Accomplishment tracking** — record career accomplishments in STAR format (Situation, Task, Action, Result), tagged for filtering, ready to feed job application materials.
- **Job application tracking** — track applications from "Interested" to "Offer".
- **Resume versioning** — multiple resume versions, tailored per job.
- **Notes, contacts & communications** — keep context and link it to any other resource.
- **Web UI** — clean interface with deep links, bookmarks, and cross-resource search.
- **MCP + REST APIs** — `/mcp` is a standard OAuth2 resource server (RFC 9728); assistants sign in via PKCE + browser, no API keys. REST at `/api`.
- **Connect page** — `/connect` (also a side panel on every page): MCP URL with one-click copy, example prompts, and verified per-assistant steps, configs, and install links for Claude, ChatGPT / Codex, ChatGPT web, Claude Code, Cursor, VS Code, Grok Build, Kiro, Devin Desktop, Zed, and Cline.
- **Docker support** — run the entire app with a single command.

## Quick Start

**Prerequisites:**

1. [Docker](https://docs.docker.com/get-docker/) + `make`
2. [Clerk](https://clerk.com) account (free tier sufficient)
3. Copy `.env.example` to `.env` and populate the Clerk env vars (see `.env.example` for required keys)

```bash
make run
```

Starts the app + a `postgres:16-alpine` container. Data persists in a named Docker volume (`pg-data`) across restarts.

Once running:

- **Web UI**: `http://localhost:8000/`
- **REST API**: `http://localhost:8000/api`
- **MCP endpoint**: `http://localhost:8000/mcp`

## Configure

| Variable | Description |
|---|---|
| `VITE_CLERK_PUBLISHABLE_KEY` | Clerk publishable key (`pk_test_...`) |
| `VITE_MCP_SERVER_URL` | Optional. Connect-tab MCP URL override. Defaults to `<page origin>/mcp` at runtime; only set it for `vite dev`, where the SPA (:5173) and backend (:8000) differ (e.g. `http://localhost:8000/mcp`) |
| `PKTX_PUBLIC_URL` | Externally reachable base URL (e.g. `https://pktx.example.com`) — required; the OAuth proxy advertises this as the authorization server and metadata base |
| `CLERK_JWKS_URL` | Clerk JWKS endpoint |
| `CLERK_ISSUER` | Clerk issuer URL |
| `CLERK_OAUTH_CLIENT_ID` | Client id of the static Clerk OAuth application the MCP proxy uses upstream |
| `CLERK_OAUTH_CLIENT_SECRET` | Client secret of that Clerk OAuth application (also derives the at-rest encryption key for proxy state) |
| `CLERK_WEBHOOK_SECRET` | Webhook signing secret from Clerk dashboard |
| `PKTX_EXTRA_CLIENT_REDIRECT_URIS` | Optional. Comma-separated redirect-URI patterns for hosted MCP clients (loopback is always allowed) |
| `CLERK_AUTHORIZED_PARTIES` | Optional. Comma-separated browser origins whose Clerk session tokens the REST API accepts (`azp` claim). Defaults to the origin of `PKTX_PUBLIC_URL`; add `http://localhost:5173` for `vite dev` |
| `PKTX_USER_ID` | stdio MCP mode only (required there): the user id tools run as. Ignored by the HTTP server |

### Keyless OAuth connect flow

MCP clients (Claude Code, Cursor, etc.) connect via standard OAuth2. The server runs an
**OAuth proxy** (FastMCP `OAuthProxy`): clients identify themselves to *us*, and we
proxy the flow upstream to Clerk through one fixed OAuth application. This removes the
loopback-redirect friction where a native client registers `http://localhost:PORT` but
sends `http://127.0.0.1:PORT` — both loopback hosts are accepted.

Both client-identification mechanisms of the MCP 2025-11-25 authorization spec are
supported: **Client ID Metadata Documents** (the spec's preferred option — the client's
`client_id` is an HTTPS URL serving its metadata, advertised by us as
`client_id_metadata_document_supported`) and **Dynamic Client Registration** at
`/register` for clients that predate CIMD.

1. Client sends unauthenticated request to `/mcp` → server returns `401` with `WWW-Authenticate` pointing to `/.well-known/oauth-protected-resource/mcp` (also served at the root `/.well-known/oauth-protected-resource`).
2. Client fetches the metadata → discovers **this server** as the authorization server.
3. Client identifies itself with a CIMD URL or registers dynamically (RFC 7591), then does a PKCE browser sign-in; the consent screen redirects to Clerk to authenticate.
4. The proxy exchanges the Clerk code server-side, stores the Clerk token encrypted **in PostgreSQL** (shared across instances — see the `oauth_kv` table), and issues the client a reference JWT bound to `aud=<PKTX_PUBLIC_URL>/mcp`. Each `/mcp` call checks that audience and re-validates the stored Clerk token, so a token minted for another resource is rejected and revocation at Clerk takes effect.

No API key to generate or paste. Add the bare URL in your assistant's MCP config —
`<your-server>/connect` has copy-ready steps for each assistant:

```bash
# Claude Code
claude mcp add --transport http pktx https://your-pktx-server.com/mcp

# Cursor / Kiro — .cursor/mcp.json or .kiro/settings/mcp.json
{ "mcpServers": { "pktx": { "url": "https://your-pktx-server.com/mcp" } } }
```

#### ChatGPT / Codex (desktop app)

Settings → **Plugins → MCPs → Add** (older builds: Settings → MCP servers → Add server).
Name it `pktx`, choose **Streamable HTTP**, paste `https://your-pktx-server.com/mcp`, leave
token/header fields empty, save (restart if asked), then click **Authenticate** and sign in
in the browser. The app signs in over a loopback callback (`http://127.0.0.1:<port>/callback/<id>`),
which the default allowlist already accepts — no extra config. It shares
`~/.codex/config.toml` with Codex CLI / IDE.

#### Hosted clients (ChatGPT web, Claude web, VS Code web, Cursor)

Hosted clients connect from their own servers (or a custom URL scheme) rather than a
loopback port, so their callbacks must be allowlisted — otherwise `/authorize` answers *"Redirect URI ... does not match
allowed patterns"*. Terraform sets this via `extra_client_redirect_uris` in
`infra/<env>/terraform.tfvars`; outside AWS, set the env var directly:

```bash
PKTX_EXTRA_CLIENT_REDIRECT_URIS=https://chatgpt.com/connector/oauth/*,https://chatgpt.com/connector_platform_oauth_redirect,https://claude.ai/api/mcp/auth_callback,https://claude.com/api/mcp/auth_callback,https://vscode.dev/redirect,cursor://anysphere.cursor-mcp/oauth/callback,https://www.cursor.com/agents/mcp/oauth/callback
```

A client not listed here fails with the same error, which prints the exact URI to add.

ChatGPT web setup:

Then, on chatgpt.com (web only; writing data needs a Business, Enterprise, or Edu plan —
Pro connects read-only; on Business only admins/owners can use developer mode, on
Enterprise/Edu an admin grants it first under Workspace Settings → Permissions & Roles →
Connected Data):

1. **Settings → Apps → Advanced settings** → turn on **Developer mode**.
2. Go to **chatgpt.com/plugins**, click **+** → **Add custom MCP server**.
3. Name it, add a description — the model reads it when deciding whether to use pktx —
   and paste `https://your-pktx-server.com/mcp` under **Connection**.
4. Pick **OAuth**, accept the risk warning, click **Create as a plugin**, and complete the
   browser sign-in. In a new chat, type **@** and pick it.

Older builds put this under **Settings → Apps → Create** (with a **Scan Tools** step).

### Clerk manual setup (required before MCP auth works end-to-end)

1. Create an OAuth application in Clerk Dashboard with redirect URI `<PKTX_PUBLIC_URL>/auth/callback`; set its client id/secret as `CLERK_OAUTH_CLIENT_ID` / `CLERK_OAUTH_CLIENT_SECRET`.
2. Confirm `<CLERK_ISSUER>/.well-known/oauth-authorization-server` advertises `authorization_endpoint` / `token_endpoint` matching `<CLERK_ISSUER>/oauth/authorize` and `/oauth/token` (adjust the proxy config if Clerk's paths differ).
3. Clients register with the proxy, not with Clerk, so Clerk-side Dynamic Client Registration is no longer required and can be left disabled.

Copy `.env.example` to `.env` and fill in values.

## Deploy to AWS (optional)

Infra as code in `infra/` using Terraform + AWS Lambda (container image). See **[docs/deployment.md](docs/deployment.md)** for the full guide including bootstrap, first-time provisioning, secrets setup, CI/CD, and teardown.

```bash
make deploy ENV=dev   # or prod
```

## Developer Setup

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for the full development workflow, conventions, and PR expectations.

### Required tools

Install once before any `make` targets:

| Tool | Version | Install |
|------|---------|---------|
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| [Node.js](https://nodejs.org/en/download) | 22+ | Official installer or preferred version manager |
| [Docker](https://docs.docker.com/get-docker/) | Any | Official installer |
| [Terraform](https://developer.hashicorp.com/terraform/install) | 1.7+ | Official installer (infra work only) |
| [Trivy](https://trivy.dev/latest/getting-started/installation/) | 0.75+ | `brew install trivy` (IaC scan in `make check`) |
| [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) | 2.x | Official installer (infra work only) |

### Install managed dependencies

```bash
make setup
```

Installs Python packages (`uv sync`) + Node packages (`npm ci`). `pip-audit` fetched automatically on first use via `uvx`.

## Make Targets

```bash
make check   # lint + typecheck + audit + test + IaC scan (frontend + backend + infra)
make run     # start app via Docker Compose
make help    # list all targets
```

## Documentation

- [docs/architecture-notes.md](docs/architecture-notes.md) — design decisions and tradeoffs
- [docs/deployment.md](docs/deployment.md) — AWS deployment guide
- [docs/rename-checklist.md](docs/rename-checklist.md) — persona → pktx rename runbook (external systems)

## License

[MIT](LICENSE)
