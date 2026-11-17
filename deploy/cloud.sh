#!/usr/bin/env bash
# Stone Growth OS cloud trial deployment; loopback-only, not production.
set -euo pipefail
umask 077
cd "$(dirname "${BASH_SOURCE[0]}")/.."

usage() {
  echo 'Usage: bash deploy/cloud.sh {up|status|stop}'
  echo 'The app binds to 127.0.0.1:8000 on the target host.'
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing dependency: $1" >&2; exit 1; }
}

secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  elif command -v python3 >/dev/null 2>&1; then
    python3 -c 'import secrets; print(secrets.token_hex(32))'
  else
    echo 'Cannot generate secrets: install openssl or python3.' >&2
    return 1
  fi
}

check_env() {
  # Strict values keep PostgreSQL connection URI interpolation unambiguous.
  # Compose loads .env; never source the file as shell code.
  if grep -Eq '^(ADMIN_API_KEY|POSTGRES_PASSWORD)=(REPLACE_|CHANGE_ME|CHANGEME|changeme|example)' .env || \
     ! grep -Eq '^ADMIN_API_KEY=[A-Za-z0-9_-]{32,}$' .env || \
     ! grep -Eq '^POSTGRES_PASSWORD=[A-Za-z0-9_-]{32,}$' .env; then
    echo '.env requires random ADMIN_API_KEY and URI-safe POSTGRES_PASSWORD (32+ chars each).' >&2
    exit 1
  fi
}

check_docker() {
  require_command docker
  docker compose version >/dev/null || { echo 'Docker Compose v2 required.' >&2; exit 1; }
  docker info >/dev/null 2>&1 || { echo 'Docker daemon unavailable or current user lacks permission.' >&2; exit 1; }
}

case "${1:-}" in
  up)
    check_docker
    require_command curl
    if [[ ! -f .env ]]; then
      admin_secret="$(secret)"
      db_secret="$(secret)"
      printf 'ADMIN_API_KEY=%s\nPOSTGRES_PASSWORD=%s\n' "$admin_secret" "$db_secret" > .env
      chmod 600 .env
      unset admin_secret db_secret
      echo 'Created .env with random secrets (not displayed).'
    fi
    check_env
    docker compose -f compose.yaml config --quiet
    docker compose -f compose.yaml up --build -d --wait --wait-timeout 120
    healthy=0
    for _ in $(seq 1 30); do
      if curl --silent --fail --max-time 2 http://127.0.0.1:8000/health >/dev/null; then
        healthy=1
        break
      fi
      sleep 2
    done
    if [[ "$healthy" -ne 1 ]]; then
      echo 'Deployment did not pass localhost health check; inspect docker compose ps.' >&2
      docker compose -f compose.yaml ps
      exit 1
    fi
    echo 'Health OK: http://127.0.0.1:8000/health'
    echo 'UI (via SSH tunnel): http://127.0.0.1:8000/'
    echo 'WARNING: MVP trial only; loopback-only. Alembic runs on startup; no SSO/RBAC or production backup/restore yet.'
    ;;
  status)
    check_docker
    docker compose -f compose.yaml ps
    if command -v curl >/dev/null 2>&1; then
      curl --silent --show-error --fail --max-time 3 http://127.0.0.1:8000/health || true
      echo
    fi
    ;;
  stop)
    check_docker
    docker compose -f compose.yaml down # keeps named PostgreSQL volume
    echo 'Services stopped; persistent database volume retained.'
    ;;
  *) usage; exit 2 ;;
esac
