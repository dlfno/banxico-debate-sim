#!/usr/bin/env bash
# Deploy a producción: git pull + rebuild de la imagen Docker con metadata de
# versión inyectada (commit SHA, fecha del commit, hora del build).
# Estos valores los lee el endpoint /api/version y los muestra en el footer.
#
# Uso:
#   ./deploy.sh           # producción (usa docker-compose.prod.yml)
#   ./deploy.sh dev       # desarrollo (usa docker-compose.yml)
#
# Asume:
# - Estás en el directorio raíz del repo (donde vive este script).
# - Tu .env ya tiene JWT_SECRET, OPENROUTER_API_KEY, BANXICO_TOKEN, etc.

set -euo pipefail

cd "$(dirname "$0")"

MODE="${1:-prod}"
if [[ "$MODE" == "prod" ]]; then
  COMPOSE_FILE="docker-compose.prod.yml"
elif [[ "$MODE" == "dev" ]]; then
  COMPOSE_FILE="docker-compose.yml"
else
  echo "Uso: $0 [prod|dev]"
  exit 1
fi

echo "▸ git pull origin main"
git pull origin main

# Captura metadata del commit actual y momento del build.
export GIT_COMMIT="$(git rev-parse --short HEAD)"
export GIT_COMMIT_DATE="$(git log -1 --format=%cI)"   # ISO-8601 con timezone
export BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "▸ Build metadata"
echo "    GIT_COMMIT=$GIT_COMMIT"
echo "    GIT_COMMIT_DATE=$GIT_COMMIT_DATE"
echo "    BUILD_TIME=$BUILD_TIME"
echo "▸ docker compose -f $COMPOSE_FILE up -d --build"

docker compose -f "$COMPOSE_FILE" up -d --build

echo "✓ Deploy completo. Verifica en /api/version o en el footer del sitio."
