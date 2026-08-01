# Plan 020 - User data export

Date: 2026-07-31

Branch: `feat/020-backups-restore-export`

Ship a user-facing "export my data" download: one authenticated request returns every record
the caller owns as a single JSON document. This is the data-portability trust story and a
blocker for the first beta invite.

**Scope change (2026-07-31, after the first PR):** this item originally also built
Terraform-managed nightly S3 backups with a restore script and drill runbook. The owner
decided against running our own backup infrastructure — Neon's own PITR is the backup story,
configured in the Neon console. All backup, restore, and drill work was removed; only the
export feature remains. See "Removed from scope" below.


## Requirements

### R1 - User data export

Any user can take their whole dataset with them.

* `GET /api/export` returns a single JSON document scoped to the caller's `user_id`:
  resumes (full data), applications, accomplishments, notes, contacts, communications, and
  resource links, plus `exported_at` and `schema_version`
* Response sets `Content-Disposition: attachment; filename="pktx-export-<date>.json"`;
  built by a new `export_service.py` reusing the existing `*_service.py` list/get calls.
  One new query was needed — `database.load_all_links` / `LinkService.list_all`, since no
  existing call returns a user's links as a flat list
* Export contains only rows owned by the caller; contract test asserts a second user's data
  never appears in the first user's export
* Frontend: "Export my data" action in `UserMenu` triggers the download through the existing
  authenticated `client.ts` fetch (blob → object URL), with success and error toasts
* Vitest covers the export action: happy path triggers a download, failure surfaces an error
  toast

### R2 - Backups stay Neon's problem

No backup infrastructure of our own, and the docs say so plainly rather than leaving a
reader to assume something exists.

* No Terraform resources, no S3 bucket, no scheduled job, no new IAM grants, no new SSM
  parameters — `infra/` is byte-identical to `main`
* No new backend dependency (`boto3` is not added)
* `docs/deployment.md` has a short Backups section stating that backups are Neon's PITR,
  configured in the Neon console, and pointing users at the export feature for their own copy


## Design

**Export is composed, not queried.** `ExportService` fans out to the existing per-resource
services rather than writing new SQL, so ownership filtering, tag parsing, and link
resolution stay in one place. List endpoints return summaries, so each record is re-fetched
by id to get full bodies (resume sections, note content, STAR fields).

**Serialization.** The route returns `JSONResponse(jsonable_encoder(data))` so datetimes
serialize the same way the rest of the API serializes them, while still allowing a custom
`Content-Disposition` header.

**Menu placement.** The action lives in Clerk's `UserButton.MenuItems` next to Manage
Account and Sign Out — where users already look for account-level operations — instead of
adding a settings page for one control.


## Removed from scope

Backups, restore, and the restore drill. Neon's PITR (Neon console → Settings → Storage →
History retention) is the backup mechanism; when it stops being enough, the answer is a Neon
plan with a longer retention window, not infrastructure here. Also still out of scope:
Markdown export format, an MCP export tool, importing an export back in, and account
deletion (item 023).


## Tasks

### P1 - Export (backend)

- [x] T01 `export_service.py` — `export_user_data(user_id) -> dict` composed from existing
      services
- [x] T02 `database.load_all_links` + `LinkService.list_all` for the flat link list
- [x] T03 `GET /api/export` route with attachment `Content-Disposition`
- [x] T04 Contract tests: export contains all owned resource types with full bodies;
      cross-user isolation in both directions

### P2 - Export (frontend)

- [x] T05 `services/api/export.ts` — `fetchDataExport` (filename from header, dated
      fallback) and `saveBlob`
- [x] T06 "Export my data" item in `UserMenu` (blob download, success/error toasts)
- [x] T07 Vitest for the export client and the menu action (success + failure)

### P3 - Backup removal

- [x] T08 Delete `backup_service.py`, `restore_service.py`, `scripts/restore_backup.py`,
      their tests, and `docs/runbooks/restore-drill.md`
- [x] T09 Revert `infra/` to `main` (backup module, EventBridge rule, IAM grant, SSM
      parameter, env wiring, outputs, variables)
- [x] T10 Drop `POST /internal/backup`, the `db_conn` router param, the backup config
      resolvers, and the `boto3` dependency
- [x] T11 Rewrite the Backups section of `docs/deployment.md` around Neon PITR; update
      `AGENTS.md` and this plan


### Implementation Notes

- The export path never touched the removed backup code, so removal is a straight deletion
  with no rework of the shipped feature.
- `make check` must be green after removal with `infra/` showing an empty diff against
  `main` — that empty diff is the real proof nothing backup-related survived.
