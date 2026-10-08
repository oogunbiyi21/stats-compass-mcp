# Security fixes for the 8 October 2026 scan

A Claude Security scan of revision `a5148a61` (0.3.31) found twelve issues.
Most come from `serve`:
- it bound every interface with no authentication;
- it offered the same file tools as local use;
- it used the raw session id as the only credential, including in links.

The statistics library had its own scan and fixes, in stats-compass-core's
`docs/audit/security-2026-10.md`. This server relies on two of them:
- core's `FilePolicy`, so it needs stats-compass-core 0.1.39 or later;
- core's expression evaluator.

| Finding | Severity | Fix |
|---|---|---|
| F1, F5, F8: `load_csv`, `load_excel`, `list_files` read any host path | HIGH, MEDIUM | Sessions confined by default (§1) |
| F2: `/download` traversal through `..` as the session id | HIGH | Signed links; paths from fixed folders (§2) |
| F3: `serve` on 0.0.0.0 with no authentication | HIGH | Loopback by default; bearer token for a public bind (§3) |
| F4: `/api/upload` wrote to a caller-chosen path | MEDIUM | Signed upload token; base name only; containment (§2) |
| F6, F7: download and upload URLs carried the session id | MEDIUM | Signed, expiring tokens (§2) |
| F9, F10: `save_csv`/`save_model` honoured absolute paths unless `STATS_COMPASS_SERVER_URL` was set | MEDIUM | Decided by the session, not the variable (§1) |
| F11: `server_stats` listed every session to anyone | LOW | Registered only for a local operator (§1) |
| F12: DEBUG log to a world-readable `/tmp` file with session ids | LOW | stderr at INFO; private file on request; short ids (§4) |

Found on the way: `register_uploaded_file` joined a caller's `file_key` to the
upload folder as given, so `../..` climbed out. Keys must now be plain names
that resolve inside the session's folder.

## 1. Sessions

`SessionManager(confine_files=True)` is the default. Each session's state gets
core's `FilePolicy`:
- writes land in `STATS_COMPASS_EXPORTS_DIR/<session>`;
- reads come from `LOCAL_STORAGE_PATH/<session>`.

**Who is confined:**
- Only `run`, the local stdio server, passes `confine_files=False`, because
  there the paths are the user's own. Anything constructing a `SessionManager`
  itself, hosted included, is confined unless it says otherwise.
- `save_csv` and `save_model` read the session's flag, never
  `STATS_COMPASS_SERVER_URL`.
- Their download link names the file actually written, which may be `x_1.csv`
  rather than overwrite.

**Admin tool:** `register_all_tools(..., include_admin=False)` leaves out
`server_stats`; only `run` registers it.

**Names:**
- A session id names folders, so it must be one path component: no `/`, `\`,
  NUL or control characters, not `.` or `..`, at most 200 characters.
- The alphabet is not restricted, because hosted ids are hashed user ids.
- Upload keys follow the same rule.

## 2. Upload and download links

`stats_compass_mcp/tokens.py` signs `purpose | session | category | file |
expiry` with HMAC-SHA256.
- **Key:** `STATS_COMPASS_SECRET_KEY`. If unset, a random key is chosen per
  process and links stop working on restart.
- **Download:** `/download/{token}`, valid for 24 hours by default
  (`STATS_COMPASS_DOWNLOAD_TTL_SECONDS`). The route rebuilds the path from the
  fixed exports folder and checks it stays inside the session's folder.
- **Upload:** `/upload?token=...`, valid for 1 hour. `/api/upload` takes the
  token, reduces the file name to a base name, and checks containment before
  writing. The page no longer shows a session id.
- **Old links break.** The old `/download/{session}/{category}/{file}` route is
  gone, so old links stop working.
- **Hosted** installs its own download builder and upload wrapper, and is
  unaffected.

## 3. `serve`

- `--host` defaults to `127.0.0.1`.
- Any other address needs a bearer token of 16 or more characters, set by
  `STATS_COMPASS_AUTH_TOKEN` or `--auth-token`. `--no-auth` allows a public bind
  without one, with a warning.
- With a token, every request except `/upload`, `/api/upload` and
  `/download/...` needs `Authorization: Bearer <token>`. Those three routes are
  exempt because their signed link is their credential.
- The Dockerfile passes `--host 0.0.0.0`, so a container without the token
  refuses to start. `docker-compose.yml` requires the token.

## 4. Logging

- The CLI logs to stderr at INFO; the stdio transport owns stdout.
- `STATS_COMPASS_LOG_FILE` adds a file, created with mode 0600.
- Session ids appear in logs cut to eight characters.

## Not covered

- **One shared token.** The bearer token is shared by every client of a
  self-hosted server. A server needing per-user identity should put an identity
  provider in front, as hosted does with Auth0.
- **Proxies and DNS rebinding.** Host and origin checks against DNS rebinding
  are left to a reverse proxy, such as the bundled Caddy.
