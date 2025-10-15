#!/usr/bin/env bash
set -euo pipefail

# --- Paths you gave me
COMPOSE_DIR="/home/fanatik/madiyar/final/docedms/backend"
ENV_FILE="/home/fanatik/madiyar/final/docedms/backend/app/.env"

# Host folder to watch (your filesystem):
HOST_SCAN="/home/fanatik/madiyar/final/docedms/backend/uploads/1/1/Projects2025"

# Inside-container mount path used by your working command:
CONTAINER_SCAN="/usr/src/app/uploads/1/1/Projects-2025"
ROOT_PREFIX="Projects-2025"

# Optional: export DB creds etc. from your .env (if present)
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

# Be nice to the disk if huge trees
IONICE=$(command -v ionice || true)
NICE=$(command -v nice || true)

cd "$COMPOSE_DIR"

# Make sure the host→container bind exists (usually in docker-compose.yml)
# Example (ensure you have the equivalent):
#   - /home/.../uploads/1/1/Projects2025:/usr/src/app/uploads/1/1/Projects-2025:ro

${IONICE:+$IONICE -c3} ${NICE:+$NICE -n 10} \
docker compose --profile manual run --rm \
  -e ROOT_SCAN="$CONTAINER_SCAN" \
  -e ROOT_PREFIX="$ROOT_PREFIX" \
  scanner

