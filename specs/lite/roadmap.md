# Roadmap

Ordered list of work items. Each item has a stable id `<NNN>` (zero-padded, 3 digits,
sequential, never reused).

Status is encoded in the title suffix:

| Suffix | Meaning |
|--------|---------|
| _(none)_ | backlog — not started |
| ` - PLANNED` | a plan exists in `specs/lite/` |
| ` - WIP` | implementation started (branch checked out) |
| ` - BUILT` | code complete, ready to commit |
| ` - SHIPPED` | committed, pushed, PR open |


## 000 Update home page with latest info - SHIPPED
Home page "Your career data, organized." shows on 2 lines, make it 1.  Show resumes, applications, accomplishments, missing notes and contacts.


## 001 Common pool of tags across all resource types - SHIPPED
Rather then separate tags for accomplishments and notes, make it common across all types. Tags added on a note should be recommended when adding a tag to accomplishment and vice versa.  Also add tags to resumes and applications. 


## 002 Add contacts feature - SHIPPED
I want a new section for "Contacts". Should have another page for contacts, allow CRUD operations on contacts, include updates to REST API, MCP tools, and UI.  Should include typical contact information as well as fields to help with work relationships and networking during job search.  Possible examples: communication preferences, interests, role, team/domain, what they care about, current priorities, collaboration opportunities, etc.  Suggest any fields that make sense for work or career related contacts without making it overly complicated, help me with this design. Think carefully about best data model.  Contacts should be taggable as well. 


## 003 Keep communication history for each contact - SHIPPED
CRUD operations for comms on contacts, and in the UI see and manage (add/edit/delete) communications. Should appear in communication section below contact details.  Support tags on communications.  Need feature to search all communication across contacts (by tag or text search), dedicated page not needed, can be feature integrated into the contacts page.


## 004 Link notes to any other resource - SHIPPED
Should use many to many relationship. Notes may be associated to applications, accomplishments, resumes, and contacts.  On the notes page should have boxes with count for each type (3 linked accomplishments, 2 linked contacts).  Click to show list of linked items, click to go to linked item. On other pages should have similar, with linked notes count, if any, click to show list, click on list item to go to note. On notes list page, should show num linked items.


## 005 Link contacts to any other resource - SHIPPED
Should use many to many relationship. Contacts may be associated to applications, accomplishments, resumes, and notes.  On the contacts page should have boxes with count for each type (3 linked accomplishments, 2 linked resumes).  Click to show list of linked items, click to go to linked item. On other pages should have similar, with linked contacts count, if any, click to show list, click on list item to go to contact.  On contacts list page, should show num linked items.  Note that this should align with the same linking approach as used for notes.


## 006 Refactor user interface to organize and reuse components - SHIPPED
Should have a `pages/` dir, separate subdir for each page with page and components specific to page.  Top level `components/` dir for shared/reusable components across pages. Improve reuse of components. Rename frontend/src/types/resume.ts, it has all types. Update AGENTS.md to explain frontend org. Suggest other high value front end refactors.


## 007 Remove application contacts and communications, use links instead - SHIPPED
Remove duplicate functionality from applications, use linked contacts and contact communications. Just have list of linked resources like all other pages. No need to preserve existing application contacts or communications, just delete (early in project, no users yet).


## 008 Adopt TanStack Query for server state - SHIPPED
Replace per-view `useEffect(fetch, [])` + manual `refresh()` pattern with `useQuery` / `useMutation`. Cache list + detail responses, dedup in-flight requests, refetch on focus, invalidate on mutate. Enables instant back-nav, optimistic updates for tag/link toggles. Replaces or thins out `useResourceList` / `useResourceDetail` hooks.


## 009 Theme tokens (CSS variables) - SHIPPED
Define `:root` CSS vars in `index.css` for spacing, colors, radii, shadows (`--space-1..8`, `--color-fg/bg/accent`, `--radius-sm/md`, `--shadow-card`). Sweep all `*.module.css` to reference vars instead of hardcoded hex/px. Enables dark mode + design-system consistency. Low risk, high visual payoff.


## 010 Toast / notification provider - SHIPPED
Replace per-view `StatusMessage` state + auto-dismiss timers with single `<ToastProvider>` at root + `useToast()` hook. Single render slot, queue, animation, no prop drilling. Cuts ~10 LOC per list/detail view.


## 011 Form abstraction (react-hook-form + zod) - SHIPPED
Replace hand-rolled field state + validation in `EntryForm`, `ContactDetailView`, `ApplicationDetailView` with `react-hook-form` (uncontrolled, fast) + `zod` schemas (single source of truth, infer TS types). Kills validation drift between client + server.


## 012 Storybook and playwright for shared components and e2e UI tests - DEFERRED
Set up Storybook targeting `frontend/src/components/`. Stories per primitive (`Breadcrumb`, `ConfirmDialog`, `EditableSection`, `LinkPickerModal`, `TagInput`, `LinksPanel`, etc.) with props matrix + a11y addon. Enables isolated visual review and future visual-regression testing (Chromatic). Defer until shared component set stabilizes. I want to set up a playwright test suite to validate the behavior of the running UI as well as validation of look and feel. It should not be part of the CI pipeline yet.

**Deferred (2026-05-23):** Too early. The shared component set is still churning — 014 (compact lists) and 015 (reusable search component) will reshape the exact primitives Storybook would document, so stories + visual baselines would rot immediately. Playwright e2e has standalone value, but keeping it out of CI on a solo project means it won't run and will rot. Revisit after 013/014/015 settle the UI; then add a thin CI-gated Playwright smoke suite first, and Storybook only if a real shared-primitive library or collaborators emerge. Plan drafted at `specs/lite/012-storybook-playwright-plan.md` (on hold).


## 013 Remove application to resume duplicate linking mechanism, use generic links - SHIPPED
`application.resume_version_id` FK duplicates the generic `link` table edge `application↔resume`. Drop the column and the matching `Application.resume_version_id` / `ApplicationSummary.resume_version_id` model fields, the `resume_version_id` param on `application_tools.py` create/update, and the resume-picker UI in `ApplicationDetailView` (replace with the standard `LinksPanel` resume entries). Replace `ResumeVersion.app_count` (currently a JOIN aggregate over the FK) with the existing generic `link_count` filtered to `type=application`, and update the resume list-card "X applications" badge accordingly. Migration must backfill existing `resume_version_id` values into `link` rows before dropping the column. No "primary resume per application" semantics preserved — generic links allow many resumes per app with no primary; revisit with a `primary_resume_link_id` flag only if the UX requires it.


## 014 Render lists in more compact form - SHIPPED
Resume list items look good, make other list items similar, more compact, fit all on one line where possible, 2 if not, float right for things like dates, link counts, etc. The goal is clean, good looking, and compact to show more items at once.


## 015 Consistent search experience - SHIPPED
Create a single search bar as a reusable component that is consistent across the application. Both tags and text in a single search bar. As you type it should recommend tags, use tab to complete the tag, or click on item from recommendations list.  When tag added, add as a chip in search bar, float left.  Any typed text that is not part a tag is used as search text. For all object types we can search by tags or text, consistent experience. There should also be a generic search API across all resources, and a search bar on the home page tha returns results for any resource.


## 016 OAuth2 MCP server auth (drop API keys) - SHIPPED
Replace MCP API-key/dual-auth with standard OAuth2. MCP client points at URL only; unauthenticated request returns 401 + `WWW-Authenticate` pointing to RFC 9728 protected-resource metadata. Clerk is the authorization server (Dynamic Client Registration). Server is a resource server only: validates bearer tokens via FastMCP `RemoteAuthProvider` + `JWTVerifier`, no key config. Home page connect UI simplified to bare URL snippets with OAuth browser sign-in copy.


## 017 DCR loopback proxy for MCP auth (FastMCP OAuthProxy) - SHIPPED
Native MCP clients (Claude Desktop, Cursor, VS Code) register one loopback redirect (`http://localhost:PORT/callback`) but send the other (`http://127.0.0.1:PORT/callback`) — per OAuth these are distinct strings, so Clerk's exact-match `redirect_uri` validation rejects the authorize call even though it's the same address. Fix: replace the 016 `RemoteAuthProvider` with FastMCP's `OAuthProxy`. The server now handles Dynamic Client Registration locally (both `localhost`/`127.0.0.1` loopback patterns accepted), proxies authorize/token upstream to one static Clerk OAuth app via a fixed `/auth/callback` redirect, and issues clients its own reference JWTs — each `/mcp` call re-validates the stored Clerk token so revocation still works. Clients register with us, not Clerk, which also insulates us from the Nov 2025 DCR→CIMD spec shift. Note: `clerk/mcp-tools` (the originally-named library) ships only TS client helpers + metadata generators, no server-side proxy — FastMCP's `OAuthProxy` (already installed) does the job with zero new deps. Needs a HUMAN-created Clerk OAuth app (`CLERK_OAUTH_CLIENT_ID`/`_SECRET`) before end-to-end auth works. Refs: https://github.com/clerk/mcp-tools, https://blog.modelcontextprotocol.io/posts/client_registration/


## 018 Lambda keep-warm EventBridge rule - SHIPPED
Cold starts hurt the MCP connect flow (Claude Desktop hits `/mcp` at session start) and first browser load. Add an EventBridge Scheduler rule to `infra/modules/lambda` (or a small sibling module) that pings the Lambda every 5 minutes to keep one instance warm. Ping a cheap unauthenticated endpoint (e.g. `/health` — add one if missing) so the warmer doesn't need Clerk credentials; handler should short-circuit before touching Postgres. Wire into both `infra/dev` and `infra/prod`. Costs stay in free tier (EventBridge + ~8.6k invocations/month). Known limits, acceptable for single-user app: concurrent second request and first post-deploy request still cold.


## 019 Rename the app to pktx and clean up docs - SHIPPED
I want to rename this app from persona to pktx which is short for personal context. Look through docs, readme, code, etc.  I also want to clean up docs and readmes, organize the repo, prep for open source. Create contributing.md. Give manual steps needed to rename all places (github, neon, clerk, etc.)


## 020 User data export - SHIPPED
Add a user-facing "export my data" feature: full dump of the user's accomplishments, applications, resumes, notes, contacts, and communications as JSON (optionally Markdown). Export is the data-portability trust story. Blocker for first beta invite. Backups are deliberately out of scope — Neon's own PITR is the backup story, configured in the Neon console, with no Terraform-managed backup infrastructure of our own.


## 021 Error tracking and feedback loop
Add error tracking (Sentry free tier or similar) for backend and frontend, wired to alert the developer on new errors. Add one low-friction in-app feedback channel (footer link to a form or shared chat). Goal: see errors before beta users report them, and make giving feedback effortless.


## 022 Deploy prod and self-host daily (beta readiness)
Stand up the prod environment (`infra/prod`) and use the app daily for 2 weeks before inviting beta users. Fix all friction found: first-run experience with empty states, signup-to-first-accomplishment under 5 minutes, MCP connect flow verified on a machine other than the dev box. Beta invite gated on this soak period completing without broken flows.


## 023 Trust basics for public launch: privacy policy, ToS, account deletion
Add privacy policy and terms of service pages. Implement full account deletion (user-initiated, via Clerk webhook cascade to all owned resources). Set an AWS budget alarm to cap surprise costs from a free public service. Required before opening signup beyond friends and family.


## 024 Donations via simple payment link
Add a GitHub Sponsors or Buy Me a Coffee link in the app footer. Explicitly no billing system, subscriptions, or tiers — a payment link only. Revisit with real billing (Stripe) only if donations become meaningful revenue.
