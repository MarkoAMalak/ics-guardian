# ICS Guardian - website + accounts

The FastAPI service now also serves a multi-page website with real login/register
and role-based access. Everything runs together in one container.

## Run it

```bash
cd platform
docker compose up --build
```

Then open **http://localhost:8000** - that is the website (home page).
The API lives on the same origin: /score, /auth/*, /health, /metrics, /docs.

## Pages

Home · About & Results · Architecture · Live Demo · SOC Dashboard · Console ·
DevSecOps · Monitoring · Media · Login · Register · My Account · Admin.
The logo sits at the top-right of every page.

## Accounts and roles

Two accounts are seeded automatically on first run:

| Role      | Email                        | Password        |
|-----------|------------------------------|-----------------|
| admin     | admin@icsguardian.local      | Admin@12345     |
| operator  | operator@icsguardian.local   | Operator@12345  |

### What each role can do (enforced in the API, shown in the UI)

| Capability                         | operator | admin |
|------------------------------------|:--------:|:-----:|
| Run the detector on your own data  |    ✓     |   ✓   |
| View the dashboards                |    ✓     |   ✓   |
| Manage your own account            |    ✓     |   ✓   |
| Change your own password           |    ✓     |   ✓   |
| List / manage all users            |          |   ✓   |
| Change a user's role               |          |   ✓   |
| Enable / disable an account        |          |   ✓   |
| View system activity               |          |   ✓   |
| Change the live detection threshold|          |   ✓   |

- **operator** - the day-to-day user: runs the detector (My Account / Console) and
  views dashboards. Cannot reach any `/admin/*` or `/auth/users*` endpoint (403).
- **admin** - everything an operator can do, plus the **Admin** panel: manage users,
  enable/disable accounts, change roles, view activity, and change the live threshold.
- Disabled accounts cannot log in. An admin cannot disable or demote their own account.
- Public **self-signup** (Register) always creates an **operator**.
- The capabilities are defined once in `auth.py` (`CAPABILITIES`) and returned by
  `/auth/me`, so the UI and the API never drift apart.

Change these demo passwords for anything real, and set a strong `AUTH_SECRET`.

## How the auth works (secure by design)

- Passwords are hashed with **PBKDF2-HMAC-SHA256** (200k rounds, per-user salt).
  Plaintext passwords are never stored.
- Sessions use a signed **JWT** (HS256); the browser keeps it in sessionStorage.
- Users live in a small **SQLite** DB at `detection_service/data/users.db`.
- Endpoints: `POST /auth/register`, `POST /auth/login`, `GET /auth/me`,
  `GET /auth/users` (admin), `POST /auth/users/{email}/role` (admin).

## Production notes (if you host it for real users)

- Set `AUTH_SECRET` to a long random value (env var).
- Serve over **HTTPS** (put it behind a reverse proxy / ingress with TLS).
- Add rate-limiting on the auth endpoints and email verification.
- The SQLite DB path (`/app/data`) must be writable; on Kubernetes with a
  read-only root filesystem, mount a small writable volume there.

## Configuration (env vars)

| Var             | Default                         | Meaning                        |
|-----------------|---------------------------------|--------------------------------|
| AUTH_SECRET     | dev-only-change-me...           | JWT signing key (set in prod)  |
| AUTH_DB         | detection_service/data/users.db | SQLite user store              |
| AUTH_TOKEN_TTL  | 28800 (8h)                      | token lifetime in seconds      |
| WEB_DIR         | detection_service/web           | website root served at /       |
