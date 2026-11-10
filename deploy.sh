#!/usr/bin/env bash
# Deploy DYLY ERP with Docker Compose: pull the latest code, build images,
# apply database migrations, then restart the stack and wait for it to be healthy.
#
# Usage: ./deploy.sh [options]
#   -b, --branch NAME   Git branch to deploy (default: $DEPLOY_BRANCH or the current branch)
#   -r, --remote NAME   Git remote to pull from (default: $DEPLOY_REMOTE or origin)
#       --host ADDRESS  Public IP or hostname, used only when creating .env (default: auto-detected)
#       --port PORT     Public HTTP port, used only when creating .env (default: 80)
#       --install-cron  After deploying, add a cron job that auto-deploys new commits every 5 minutes
#       --dev           Use the development compose files instead of production
#       --no-pull       Skip git fetch/pull and deploy the current checkout
#       --no-build      Reuse existing images instead of rebuilding
#       --skip-migrate  Do not run database migrations
#       --skip-backup   Do not back up the database before applying migrations
#   -f, --force         Deploy even when the remote has no new commits
#   -h, --help          Show this help
#
# First run on a fresh server (Ubuntu/Debian):
#   git clone <repo-url> ~/dyly-erp && cd ~/dyly-erp && ./deploy.sh --install-cron
# This installs Docker if it is missing, writes .env with generated secrets,
# seeds the Super Admin when the database has none, and serves the app on port 80.
#
# After editing .env, apply it with: ./deploy.sh --force
#
# Before pending migrations are applied, the database is dumped to
# backups/db-<timestamp>.sql.gz. The newest $BACKUP_KEEP dumps are kept (default 10).

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"
ORIGINAL_ARGS=("$@")

BRANCH="${DEPLOY_BRANCH:-}"
REMOTE="${DEPLOY_REMOTE:-origin}"
PUBLIC_HOST="${DEPLOY_HOST:-}"
PUBLIC_PORT="${DEPLOY_PORT:-80}"
MODE=production
PULL=true
BUILD=true
MIGRATE=true
BACKUP=true
BACKUP_KEEP="${BACKUP_KEEP:-10}"
BACKUP_FILE=""
INSTALL_CRON=false
FORCE=false
USE_SUDO=false
PREVIOUS_COMMIT="${DEPLOY_PREVIOUS_COMMIT:-}"
COMPOSE=()

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
warn() { log "WARNING: $*" >&2; }
die() { log "ERROR: $*" >&2; exit 1; }
usage() { sed -n '2,/^$/{s/^# \{0,1\}//;p}' "$SCRIPT_DIR/$SCRIPT_NAME"; }
as_root() { if ((EUID == 0)); then "$@"; else sudo "$@"; fi; }
as_docker_user() { if $USE_SUDO; then sudo "$@"; else "$@"; fi; }
compose() { as_docker_user "${COMPOSE[@]}" "$@"; }
env_value() { sed -n "s/^$1=//p" .env | tail -n 1 | tr -d "\"'\r"; }
random_hex() { od -An -N"$1" -tx1 /dev/urandom | tr -d ' \n'; }

on_error() {
  local code=$?
  log "Deploy failed (exit $code)." >&2
  if [[ -n "$PREVIOUS_COMMIT" ]]; then
    log "Code before this deploy: ${PREVIOUS_COMMIT:0:7}. Roll back with: git checkout $PREVIOUS_COMMIT && ./$SCRIPT_NAME --no-pull" >&2
    log "Rolling back code does not revert migrations that already ran." >&2
  fi
  if [[ -n "$BACKUP_FILE" ]]; then
    log "Database backup taken before migrations: $BACKUP_FILE" >&2
  fi
  if [[ ${#COMPOSE[@]} -gt 0 ]]; then
    log "Inspect logs with: ${COMPOSE[*]} logs --tail=100" >&2
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -b|--branch)
        [[ $# -ge 2 ]] || die "$1 needs a value"
        BRANCH="$2"; shift 2 ;;
      -r|--remote)
        [[ $# -ge 2 ]] || die "$1 needs a value"
        REMOTE="$2"; shift 2 ;;
      --host)
        [[ $# -ge 2 ]] || die "$1 needs a value"
        PUBLIC_HOST="$2"; shift 2 ;;
      --port)
        [[ $# -ge 2 ]] || die "$1 needs a value"
        PUBLIC_PORT="$2"; shift 2 ;;
      --install-cron) INSTALL_CRON=true; shift ;;
      --dev) MODE=development; shift ;;
      --no-pull) PULL=false; shift ;;
      --no-build) BUILD=false; shift ;;
      --skip-migrate) MIGRATE=false; shift ;;
      --skip-backup) BACKUP=false; shift ;;
      -f|--force) FORCE=true; shift ;;
      -h|--help) usage; exit 0 ;;
      *) usage >&2; die "Unknown option: $1" ;;
    esac
  done
}

acquire_lock() {
  command -v flock >/dev/null 2>&1 || return 0
  exec 9>"${TMPDIR:-/tmp}/dyly-erp-deploy.lock"
  flock -n 9 || die "Another deploy is already running."
}

install_docker() {
  command -v apt-get >/dev/null 2>&1 \
    || die "Docker is not installed. Install Docker Engine with the Compose plugin, then rerun."
  log "Installing Docker Engine and the Compose plugin"
  if ! command -v curl >/dev/null 2>&1; then
    as_root apt-get update -q
    as_root apt-get install -y -q curl ca-certificates
  fi
  curl -fsSL https://get.docker.com | as_root sh
  as_root systemctl enable --now docker
  if ((EUID != 0)); then
    as_root usermod -aG docker "$(id -un)"
  fi
}

ensure_docker() {
  command -v docker >/dev/null 2>&1 || install_docker

  if ! docker info >/dev/null 2>&1; then
    if ((EUID != 0)) && sudo docker info >/dev/null 2>&1; then
      log "$(id -un) cannot reach Docker directly yet (log out and back in to pick up the docker group); using sudo for this run"
      USE_SUDO=true
    else
      die "Docker daemon is not reachable. Is it running, and can this user access it?"
    fi
  fi
}

detect_compose() {
  if as_docker_user docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose)
  elif command -v docker-compose >/dev/null 2>&1 && [[ "$(as_docker_user docker-compose version --short 2>/dev/null)" == 2* ]]; then
    COMPOSE=(docker-compose)
  else
    die "Docker Compose v2 is required (docker compose plugin or docker-compose 2.x)."
  fi

  if [[ "$MODE" == production ]]; then
    COMPOSE+=(-f compose.yaml -f compose.prod.yaml)
  fi
}

detect_public_host() {
  local host
  host="$(curl -fsS4 --max-time 5 https://api.ipify.org 2>/dev/null || true)"
  if [[ -z "$host" ]]; then
    host="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
  fi
  printf '%s' "$host"
}

create_env() {
  local host="${PUBLIC_HOST:-$(detect_public_host)}"
  [[ -n "$host" ]] || die "Could not detect this server's public IP. Pass it with --host ADDRESS."
  local url="http://$host"
  [[ "$PUBLIC_PORT" == 80 ]] || url+=":$PUBLIC_PORT"

  log "Creating .env for $url with generated secrets"
  cat > .env <<EOF
# Generated by $SCRIPT_NAME on $(date '+%Y-%m-%d'). After editing, run: ./$SCRIPT_NAME --force
SECRET_KEY=$(random_hex 32)
ALLOWED_HOSTS=$host,localhost,127.0.0.1,backend

POSTGRES_DB=erp
POSTGRES_USER=erp
POSTGRES_PASSWORD=$(random_hex 16)

# Public address of the app. nginx on HTTP_PORT serves the frontend and proxies
# /api, /admin, /static and /media to Django. Include the port in the URLs unless it is 80.
HTTP_PORT=$PUBLIC_PORT
FRONTEND_URL=$url
BACKEND_URL=$url
VITE_API_BASE_URL=$url

# Outgoing email. While EMAIL_BACKEND is empty, emails are only printed to the backend log.
# For Gmail: EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend and an app password.
EMAIL_BACKEND=
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=
USER_INVITE_EXPIRY_HOURS=48
EOF
  chmod 600 .env
}

check_env() {
  [[ "$MODE" == production ]] || return 0
  [[ -f .env ]] || create_env

  local secret
  secret="$(env_value SECRET_KEY)"
  if [[ -z "$secret" || "$secret" == "dev-only-change-me" ]]; then
    die "Set a real SECRET_KEY in .env before deploying to production."
  fi

  local key
  for key in ALLOWED_HOSTS FRONTEND_URL BACKEND_URL VITE_API_BASE_URL; do
    if [[ -z "$(env_value "$key")" || "$(env_value "$key")" == *localhost:* ]]; then
      warn "$key in .env is '$(env_value "$key")'. Set it to this server's public address or the app will not work from other machines."
    fi
  done
  if [[ -z "$(env_value EMAIL_BACKEND)" ]]; then
    warn "EMAIL_BACKEND is empty in .env, so invite and password-reset emails are not sent."
  fi
}

stack_running() {
  [[ -n "$(compose ps -q --status running backend 2>/dev/null)" ]]
}

check_http_port() {
  [[ "$MODE" == production ]] || return 0
  command -v ss >/dev/null 2>&1 || return 0
  # On redeploys our own frontend container already holds the port.
  [[ -z "$(compose ps -q --status running frontend 2>/dev/null)" ]] || return 0

  local port
  port="$(env_value HTTP_PORT)"
  port="${port:-80}"
  if ss -ltn "sport = :$port" | tail -n +2 | grep -q .; then
    die "Port $port is already in use on this server. In .env set HTTP_PORT to a free port and add it to FRONTEND_URL, BACKEND_URL and VITE_API_BASE_URL (e.g. http://HOST:8080), then run ./$SCRIPT_NAME --force."
  fi
}

pull_code() {
  command -v git >/dev/null 2>&1 || die "git is not installed."
  git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || die "$SCRIPT_DIR is not a git checkout. Use --no-pull to deploy the files as they are."
  [[ -z "$(git status --porcelain --untracked-files=no)" ]] \
    || die "Tracked files have local changes. Commit or stash them before deploying."

  BRANCH="${BRANCH:-$(git rev-parse --abbrev-ref HEAD)}"
  [[ "$BRANCH" != HEAD ]] || die "Checkout is in detached HEAD state. Pass --branch."

  log "Fetching $REMOTE/$BRANCH"
  git fetch --prune "$REMOTE" "$BRANCH"
  if [[ "$(git rev-parse --abbrev-ref HEAD)" != "$BRANCH" ]]; then
    git checkout "$BRANCH"
  fi

  PREVIOUS_COMMIT="$(git rev-parse HEAD)"
  if [[ "$PREVIOUS_COMMIT" == "$(git rev-parse "$REMOTE/$BRANCH")" ]]; then
    if ! $FORCE && stack_running; then
      log "Already up to date at ${PREVIOUS_COMMIT:0:7}. Nothing to deploy (use --force to redeploy)."
      if $INSTALL_CRON; then install_cron; fi
      exit 0
    fi
    return 0
  fi

  local script_before
  script_before="$(git hash-object "$SCRIPT_NAME")"
  git merge --ff-only "$REMOTE/$BRANCH" \
    || die "Local $BRANCH has diverged from $REMOTE/$BRANCH. Resolve it manually."
  log "Code updated ${PREVIOUS_COMMIT:0:7} -> $(git rev-parse --short HEAD)"

  if [[ "$(git hash-object "$SCRIPT_NAME")" != "$script_before" ]]; then
    log "$SCRIPT_NAME changed in this update; continuing with the new version"
    DEPLOY_PREVIOUS_COMMIT="$PREVIOUS_COMMIT" \
      exec bash "$SCRIPT_DIR/$SCRIPT_NAME" ${ORIGINAL_ARGS[@]+"${ORIGINAL_ARGS[@]}"} --no-pull
  fi
}

build_images() {
  log "Building images"
  compose build --pull
}

run_migrations() {
  log "Starting PostgreSQL and Redis"
  compose up -d --wait postgres redis

  log "Checking for model changes that are missing migrations"
  compose run --rm --no-deps -T backend python manage.py makemigrations --check --dry-run

  if compose run --rm --no-deps -T backend python manage.py migrate --check >/dev/null 2>&1; then
    log "No pending migrations"
  else
    if $BACKUP; then backup_database; fi
    log "Applying database migrations"
    compose run --rm --no-deps -T backend python manage.py migrate --noinput
  fi

  seed_superadmin
}

seed_superadmin() {
  local has_superuser="from django.contrib.auth import get_user_model; import sys; sys.exit(0 if get_user_model().objects.filter(is_superuser=True).exists() else 3)"
  local code=0
  compose run --rm --no-deps -T backend python manage.py shell -c "$has_superuser" >/dev/null 2>&1 || code=$?
  ((code == 3)) || return 0

  log "No Super Admin in the database; seeding the default account"
  compose run --rm --no-deps -T backend python manage.py seed_superadmin
  warn "Log in and change the default Super Admin password now."
}

backup_database() {
  mkdir -p backups
  local file
  file="backups/db-$(date '+%Y%m%d-%H%M%S').sql.gz"

  log "Backing up database to $file"
  # shellcheck disable=SC2016 # expanded by the shell inside the postgres container
  compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' | gzip > "$file.partial"
  mv "$file.partial" "$file"
  BACKUP_FILE="$file"

  local backups=(backups/db-*.sql.gz)
  local excess=$((${#backups[@]} - BACKUP_KEEP))
  if ((excess > 0)); then
    log "Removing $excess old backup(s), keeping the newest $BACKUP_KEEP"
    rm -f -- "${backups[@]:0:excess}"
  fi
}

start_stack() {
  log "Starting services and waiting for health checks"
  compose up -d --remove-orphans --wait
  compose ps
}

verify_public_entrypoint() {
  [[ "$MODE" == production ]] || return 0
  log "Checking the API through nginx"
  local health
  health="$(compose exec -T frontend wget -qO- http://127.0.0.1/api/v1/health/)" \
    || die "nginx is up but cannot reach the backend API."
  log "Health: $health"
}

install_cron() {
  command -v crontab >/dev/null 2>&1 || die "crontab is not installed (apt-get install cron)."
  local job="cd \"$SCRIPT_DIR\" && ./$SCRIPT_NAME"
  [[ -z "$BRANCH" ]] || job+=" --branch $BRANCH"
  local line="*/5 * * * * $job >> \"$SCRIPT_DIR/deploy.log\" 2>&1"

  local existing
  existing="$(crontab -l 2>/dev/null || true)"
  if grep -Fq -- "cd \"$SCRIPT_DIR\" && ./$SCRIPT_NAME" <<< "$existing"; then
    log "Auto-deploy cron job already installed"
    return 0
  fi
  printf '%s\n' "$existing" "$line" | sed '/^$/d' | crontab -
  log "Installed auto-deploy cron job (every 5 minutes, log: deploy.log)"
}

main() {
  parse_args "$@"
  cd "$SCRIPT_DIR"
  trap on_error ERR
  acquire_lock

  log "Deploying DYLY ERP ($MODE)"
  ensure_docker
  detect_compose
  check_env
  check_http_port

  if $PULL; then pull_code; fi
  if $BUILD; then build_images; fi
  if $MIGRATE; then run_migrations; fi
  start_stack
  verify_public_entrypoint

  log "Removing dangling images"
  as_docker_user docker image prune -f >/dev/null

  if $INSTALL_CRON; then install_cron; fi

  log "Deploy finished at $(git rev-parse --short HEAD 2>/dev/null || echo 'local files')"
  if [[ "$MODE" == production ]]; then
    local port
    port="$(env_value HTTP_PORT)"
    log "DYLY ERP is available at $(env_value FRONTEND_URL)"
    log "If it does not open from other machines, allow it in the firewall: sudo ufw allow ${port:-80}/tcp"
  fi
}

main "$@"
