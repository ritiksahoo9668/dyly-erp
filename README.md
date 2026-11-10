# DYLY ERP

Phase 1 is the technical foundation and application shell. Procurement, Production, Sales, HR, and Master are navigation placeholders. Business workflows, transaction models, and integrations are not part of this phase.

## Services

`docker compose up` starts:

- Frontend on http://localhost:5173
- Backend on http://localhost:8000
- PostgreSQL on localhost:5433 (container port 5432)
- Redis on localhost:6380 (container port 6379)
- Celery worker
- Celery Beat

Host ports 5433 and 6380 avoid clashing with a PostgreSQL or Redis instance already listening on 5432 and 6379. Containers still talk to each other on the Compose network.

## Docker startup

```bash
docker compose up --build
```

Development ports and source mounts come from `compose.override.yaml`, which Docker Compose loads automatically.

Production-style overrides are in `compose.prod.yaml`. Set a real `SECRET_KEY` before using them:

```bash
docker compose -f compose.yaml -f compose.prod.yaml up --build
```

## Production server

On a fresh Ubuntu/Debian server, clone the repo and run the deploy script:

```bash
git clone <repo-url> ~/dyly-erp
cd ~/dyly-erp
./deploy.sh --install-cron
```

It installs Docker if needed, creates `.env` with generated secrets and the server's public IP, seeds the Super Admin on an empty database, and serves everything on port 80, or `HTTP_PORT` from `.env` (nginx proxies `/api`, `/admin`, `/static` and `/media` to Django). The cron job redeploys within 5 minutes of a new push. After editing `.env`, run `./deploy.sh --force`. See `./deploy.sh --help` for all options.

Migrations are applied only by `deploy.sh`, never on container start. Before applying them it lists the pending migrations and saves a verified dump to `backups/db-<timestamp>.sql.gz`; until they succeed the old containers keep serving. If a deploy fails, the log prints the exact rollback command, for example:

```bash
git checkout <previous-commit> && ./deploy.sh --restore backups/db-<timestamp>.sql.gz
git checkout main   # afterwards, so auto-deploy resumes
```

Always create migrations locally (`python manage.py makemigrations`) and commit them; a deploy stops if models changed without a migration file.

Copy environment defaults if you want a local env file. Compose already has development defaults, so this is optional:

```bash
cp .env.example .env
```

## Health check

```bash
curl http://localhost:8000/api/v1/health/
```

Expected shape when PostgreSQL and Redis are reachable:

```json
{"status": "ok", "database": "ok", "redis": "ok"}
```

The frontend calls this endpoint and shows a service status in the header.

## Routes

- `/dashboard`
- `/procurement`
- `/production`
- `/sales`
- `/hr`
- `/master`

`/` redirects to `/dashboard`. The Procurement menu lists future stages, but those items do not open routes.

## Local commands

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Backend, with PostgreSQL and Redis already running:

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements/development.txt
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py runserver
```

## Not in Phase 1

No procurement stages, master data, production, sales, or HR transactions. No approval workflow, notifications, reports, or SAP, Tally, email, or AI integrations.
