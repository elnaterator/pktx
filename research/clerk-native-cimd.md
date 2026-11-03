# Clerk native CIMD vs our OAuth proxy

Question: Clerk now supports Client ID Metadata Documents (beta 2026-08-05, GA 2026-09-17). Can we delete the FastMCP `OAuthProxy` (`auth.build_mcp_auth`, `oauth_store.py`, `oauth_kv`) and let MCP clients talk to Clerk directly?

## What Clerk CIMD does (from docs + changelog)

- Client `client_id` is an HTTPS URL with a path; Clerk fetches the document, checks `client_id` matches the URL, needs a client name and at least one `redirect_uris`.
- Every CIMD client is public: PKCE S256 required, consent screen always shown, secret-based auth methods rejected.
- Off by default. Enable "Publish CIMD support" (OAuth applications → Client onboarding). Advertises `client_id_metadata_document_supported` in AS metadata.
- Admission: any CIMD client by default (recorded on first connect), or "Pre-registered clients only"; per-client scopes set in the CIMD Clients tab.
- Scopes: "Default scopes for dynamic clients" apply when `scope` omitted (at least one required); `offline_access` always included.
- Requires Clerk's **new** OAuth implementation, not legacy.
- Redirect URI must **exactly match** an entry in the document's `redirect_uris`.

## Not covered by the docs (the spike must answer)

- Loopback tolerance: nothing says `localhost` vs `127.0.0.1` is relaxed. Exact match implies the bug 017 fixed returns.
- Audience: no mention of RFC 8707 `resource`. Clerk token `aud` is a Clerk client id today; MCP 2025-11-25 requires tokens bound to our resource.
- Token format, revocation, introspection.
- Consent page branding (needs Account Portal or configured consent page).

## What the proxy gives us today (what must be matched or consciously dropped)

1. Loopback-tolerant redirects (`DEFAULT_LOCALHOST_PATTERNS`).
2. Proxy JWTs bound to `aud=<PKTX_PUBLIC_URL>/mcp`, wrong audience rejected.
3. Revocation-aware: each call swaps proxy JWT for stored Clerk token and re-validates.
4. Own themed consent page, `PKTX_EXTRA_CLIENT_REDIRECT_URIS` allowlist for hosted clients (ChatGPT, 026).
5. DCR fallback for older clients.

Native Clerk would drop DCR for clients that lack CIMD; check which of Claude Desktop, Cursor, VS Code, ChatGPT send CIMD today.

## Clerk OAuth app settings (current proxy setup)

- `openid` in default scopes: yes (need `sub`).
- Require PKCE: yes, only if the proxy forwards `code_challenge` upstream; verify with one login.
- Audience: leave empty; verifier uses `audience=None` for the upstream Clerk token.

## Verdict (2026-11-02): no-go, spike dropped

Desk check against current Clerk docs (no live spike):

| Criterion | Status | Evidence |
|---|---|---|
| 1. Loopback `localhost` vs `127.0.0.1` | Likely fail | Redirect must "exactly match" a `redirect_uris` entry; no loopback/port relaxation documented. |
| 2. `aud` bound to `<PKTX_PUBLIC_URL>/mcp` (RFC 8707) | Likely fail | No `resource` parameter documented anywhere in Clerk OAuth docs; `aud` is the client id. MCP spec MUST. |
| 3. Revocation-aware | Fixable | OAuth app can issue opaque access tokens (introspection, instant revoke). JWT default is not. |
| 4. Consent page + hosted allowlist | Acceptable | Consent always shown (Account Portal or custom page); lose our themed page. |
| 5. `client_id_metadata_document_supported` | Pass | Advertised when "Publish CIMD support" is on. DCR toggle still exists. |

Also: Clerk's `acceptsToken` helpers are Node-only; Python would need a hand-written verifier.

Payoff (delete `OAuthProxy`, `oauth_store.py`, `oauth_kv`, one secret) does not justify losing (1), (2) and the themed consent page. The proxy keeps MCP auth IdP-agnostic, so it stays.

### Other IdPs (considered, rejected)

- Auth0: CIMD GA (May 2026) but registration appears admin-driven per client URL; RFC 8707 via "resource parameter compatibility mode".
- Okta: reportedly no `resource` support.
- WorkOS AuthKit: claims CIMD + DCR + RFC 8707 (vendor claim); strongest on paper.
- Stytch: partial CIMD, RFC 8707 yes. Descope: CIMD + DCR, RFC 8707 unclear. Keycloak: CIMD experimental, self-host.

Migration cost (Clerk React SDK, REST JWT auth, `user_id` = Clerk `sub` across all tables) outweighs any gain while the proxy works.

### Re-check trigger

Clerk documents RFC 8707 resource indicators **and** loopback redirect tolerance (watch https://clerk.com/changelog). Then a 15-minute probe settles it: authorize with `resource=<PKTX_PUBLIC_URL>/mcp`, inspect `aud`; authorize a CIMD client listing `127.0.0.1` with `redirect_uri=http://localhost:<port>`.

### Additional sources

- https://clerk.com/docs/guides/configure/auth-strategies/oauth/how-clerk-implements-oauth.md
- https://releases.sh/release/rel_RkU7ogmtV4G8A6NgZpWFf-auth-for-mcp-ga-cimd-registration-and-obo-token-exchange-ready
- https://workos.com/blog/best-mcp-server-authentication-providers
- https://zuplo.com/learn/mcp/compatibility/identity-providers

## Sources

- https://clerk.com/docs/guides/configure/auth-strategies/oauth/client-id-metadata-documents
- https://clerk.com/changelog/2026-09-17-client-id-metadata-documents-ga
- https://clerk.com/changelog/2026-08-05-client-id-metadata-documents
- https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
