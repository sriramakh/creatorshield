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


Authentication verifies uncached headers in worker threads (at most two concurrently),
with at most 20 uncached attempts per minute per API process. Excess attempts return 429.
Concurrent requests carrying the same uncached header share one verification, so a page
load after the cache lapses does not exhaust the limit. Successful headers are cached
until five minutes without use, with at most 128 HMAC keys in memory;
raw headers and passwords are not cached. Caches are local to each application instance
and are cleared on restart/credential rotation. Failed credentials are never cached.
This bounds hashing work but does not replace hosting-edge request limits. During an
attack, new logins may be throttled while already cached credentials continue to work.
