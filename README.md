# MaidanPlay-June150

Rewrite of the legacy `june-one50` Google Sheets-backed SPA into a typed FastAPI + Next.js stack with proper auth, server-side permissions, and a SQLite source of truth (Postgres-bound later).

## Stack
- **Backend** — FastAPI on `:8000`, SQLite via stdlib `sqlite3`. Email/password auth with scrypt hashing and HMAC-signed bearer tokens (`pf`-bound to the current password hash, so resets invalidate sessions instantly).
- **Frontend** — Next.js 16 (App Router) + React 19, single client component `OpsApp.tsx` driving a hash-routed SPA.

## Run locally

### Backend
```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
```
On first run the SQLite DB seeds itself with users (default password `MaidanPlay@2026`), batch config, and demo students.

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:3000.

## Seed logins
Default password for all seeded users: **`MaidanPlay@2026`** (super-admin rotates per person via Admin Panel).

| Role | Sample email |
|---|---|
| Super-admin (admin) | `abhimanyu@maidanplay.com`, `ruchir@maidanplay.com` |
| Super-admin (akash) | `akash@maidanplay.com` |
| Director (amit) | `amit@maidanplay.com`, `yuvrajchawla@maidanplay.com` (Vasu) |
| P&L Head (kush) | `kush@maidanplay.com`, `mdathar@maidanplay.com` (Athar) |
| Coach | `adi@maidanplay.com`, `daksh@maidanplay.com`, `eeshan@maidanplay.com` |
| Employee | `sanjana@maidanplay.com`, `aryan@maidanplay.com`, `pranjal@maidanplay.com` |

## Environment
- `JUNE_ONE50_SECRET` — HMAC secret for bearer tokens. **Set this in production.**
- `JUNE_ONE50_DB` — override the SQLite path.
- `JUNE_ONE50_SEED_DEMO` — set `0` to skip demo students on first boot.
- `JUNE_ONE50_CORS_ORIGINS` — comma-separated allowed origins.

## Layout
```
backend/
  app/
    main.py        # routes
    logic.py       # business rules, permission checks, password hashing
    security.py    # token signing/verification (pf-bound)
    db.py          # schema, connection helpers
    models.py      # Pydantic request/response models
    config.py      # seed users, batches, field defs
  scripts/
    import_legacy_json.py
frontend/
  app/             # Next.js App Router entry
  components/
    OpsApp.tsx     # the entire client app
  lib/
    api.ts, types.ts
```
