#!/usr/bin/env bash
set -euo pipefail

# === Paths you gave me
COMPOSE_DIR="/home/fanatik/madiyar/final/docedms/backend"
ENV_FILE="/home/fanatik/madiyar/final/docedms/backend/app/.env"

# Optional: export DB creds etc. from your .env (if present)
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

# Be nice to the disk if huge trees
IONICE=$(command -v ionice || true)
NICE=$(command -v nice || true)

cd "$COMPOSE_DIR"

#######################################
# === Projects-2025
#######################################
HOST_SCAN_2025="/home/fanatik/madiyar/final/docedms/backend/uploads/1/1/Projects-2025"
CONTAINER_SCAN_2025="/usr/src/app/uploads/1/1/Projects-2025"
ROOT_PREFIX_2025="Projects-2025"

${IONICE:+$IONICE -c3} ${NICE:+$NICE -n 10} \
docker compose --profile manual run --rm \
  -e ROOT_SCAN="$CONTAINER_SCAN_2025" \
  -e ROOT_PREFIX="$ROOT_PREFIX_2025" \
  scanner

#######################################
# === Projects-2026
#######################################
HOST_SCAN_2026="/home/fanatik/madiyar/final/docedms/backend/uploads/1/1/Projects-2026"
CONTAINER_SCAN_2026="/usr/src/app/uploads/1/1/Projects-2026"
ROOT_PREFIX_2026="Projects-2026"

${IONICE:+$IONICE -c3} ${NICE:+$NICE -n 10} \
docker compose --profile manual run --rm \
  -e ROOT_SCAN="$CONTAINER_SCAN_2026" \
  -e ROOT_PREFIX="$ROOT_PREFIX_2026" \
  scanner
