# Dedicated-agency paid-pilot deployment

This deployment supports one agency per installation, with one agency operator login. It does not implement team accounts, roles or a shared multi-tenant service. Client labels are organizational labels within that agency, not access boundaries. Use an operator-reviewed pilot until individual reviewer accounts are implemented.

Each agency must have a unique Compose project name, hostname, database password, login/password hash, OAuth apps or redirect configuration, encryption key and environment file. Compose creates project-scoped networks and database/media volumes. Never reuse a project name, mount a shared media directory, share Redis, or point two agencies at the same database. Only the HTTPS gateway publishes ports; API, frontend, Redis and Postgres stay internal. Deploy separate hosts or separate IPs when running more than one gateway.

Create a fresh database for the pilot. On startup, API and worker verify the permanent agency binding; a different agency ID is refused. Existing unbound databases containing customer records are refused. Do not delete or alter the binding to repurpose a database.

Create a private environment file outside the repository, permissions 600, containing PILOT_USERNAME, PILOT_PASSWORD_HASH, TOKEN_ENCRYPTION_KEY and any provider credentials. Generate a long unique password and hash it using Python from the backend environment:

```python
from getpass import getpass
from app.auth import hash_password
print(hash_password(getpass("New agency password: ")))
```

Set deployment variables AGENCY_ID, PILOT_DOMAIN, PILOT_ENV_FILE (absolute path), PILOT_DB_PASSWORD (long URL-safe random value), and PILOT_BIND_IP (the host's intended public IP). Then run:

```sh
docker compose -p agency_unique_name -f compose.pilot.yml config --quiet
docker compose -p agency_unique_name -f compose.pilot.yml up --build -d
```

Configure DNS for the hostname and allow ports 80/443 for Caddy certificate issuance. The default bind address is loopback to avoid accidental publication. Use the dedicated compose file by itself, never as an override of docker-compose.yml (which publishes the development API). HTTPS is required in production. The browser prompts for the agency login before showing the application; API requests and downloads use the same origin. Configure OAuth callbacks at https://HOST/api/connections/PLATFORM/callback. OAuth callbacks remain authenticated.

Basic authentication intentionally has no application session or logout button. Use a dedicated browser profile; close it after use, and rotate the password hash and restart the API to revoke credentials. Do not share this operator login with separate clients. Rate limiting at the hosting edge and individual user/session management remain prerequisites for wider self-service access.

Before customer use, test real HTTPS browser login, uploads, report/video/proof downloads, OAuth callbacks and credential rotation. Verify unauthenticated requests return 401, cross-site writes return 403, and a second agency's credentials fail. Validate separate database/volume identities and backups. The automated authentication checks do not substitute for this deployment test. Other audit blockers (rights accuracy, retention, evaluation) remain separate work.


Authentication verifies uncached headers in worker threads (at most two concurrently).
Uncached attempts are limited per client (`AUTH_ATTEMPTS_PER_CLIENT_PER_MINUTE`, default
10) and in total per API process (`AUTH_ATTEMPTS_GLOBAL_PER_MINUTE`, default 120);
excess attempts return 429. The client is the address the gateway saw: the compose files
set `TRUSTED_PROXIES` to the private Docker ranges so the API reads the gateway's
`X-Forwarded-For` (Caddy replaces any value sent by the client). One anonymous client
therefore cannot lock out the operator; many clients at once can still reach the global
backstop. Concurrent requests carrying the same uncached header share one verification,
so a page load after the cache lapses does not exhaust the limit. Successful headers are
cached until five minutes without use, with at most 128 HMAC keys in memory; raw headers
and passwords are not cached. Caches are local to each application instance and are
cleared on restart/credential rotation. Failed credentials are never cached. Caddy has
no request rate limiter without plugins (e.g. `caddy-ratelimit`); use a firewall or an
edge service for request-level limits.

Gateway and operations (both compose files):

- `request_body max_size` (`MAX_REQUEST_BODY`, default 5121MB) refuses oversized uploads at
  the gateway; the API also refuses them while they arrive (413) and spools uploads on the
  media volume (`UPLOAD_TMP_DIR`), never the container's root disk. Keep `MAX_REQUEST_BODY`
  at `MAX_UPLOAD_MB` + 1 MB.
- Security headers for every response: HSTS (HTTPS gateway only), nosniff,
  `Referrer-Policy: same-origin`, `X-Frame-Options: DENY`, a Content-Security-Policy with
  `frame-ancestors 'none'` (Next.js needs `script-src 'unsafe-inline'`), Permissions-Policy.
  API responses that set their own value (the report's strict CSP) keep it.
- Every service restarts unless stopped and has a healthcheck. The API is healthy when
  `/api/health/ready` (database, Redis, writable storage) answers 200; this probe and
  `/api/health/live` need no login inside the network but are still behind the gateway login.
  The worker is healthy while it is registered in Redis (`python -m app.worker --check`).
- Maintenance runs at worker start and every `MAINTENANCE_INTERVAL_SECONDS` (default 900)
  in the API and worker, one run at a time (Postgres advisory lock): retention purge
  (analyses, fingerprints, paid-lookup records), analyses stuck in `processing`/`queued`
  after a crash reset to `failed` (Rerun works again), and stored files without a database
  row removed after `ORPHAN_GRACE_SECONDS`.

## Single-port test instance (no domain)

`deploy/compose.port.yml` runs the same stack behind one plain-HTTP port on a shared
host (for example `http://HOST:8095`). Only the Caddy gateway publishes a port; every
request passes the API login via `forward_auth`. The worker is limited to 2 CPUs and 6 GB
so other services on the host keep running. Without a domain there is no HTTPS, so the
login travels unencrypted: use it for internal testing only, and `compose.pilot.yml`
with a domain for customers. Production mode requires HTTPS, so this instance runs with
`APP_ENV=development` and `REQUIRE_LOGIN=true`: API and worker refuse to start unless
`PILOT_USERNAME` / `PILOT_PASSWORD_HASH` are set. Set `AGENCY_ID` as well to bind the
database to one agency as in production.

On the test host the instance lives in `/opt/creatorshield` (`app/` is a clone of this
repo; `creatorshield.env` and `db_password` are root-only). `./up.sh [git ref]` fetches,
rebuilds and restarts it (default `origin/main`).
