#!/usr/bin/env bash
set -euo pipefail

# Quick Wiki.js setup script for Debian
# Place this in docs/wiki/ and run from that folder on the Debian host.
# It expects your project .env to be at ../.env (repo root). It will copy it locally
# and run `docker compose` to start the Wiki.js container.

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WIKI_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE_SRC="$REPO_ROOT/.env"
ENV_FILE_DEST="$WIKI_DIR/.env"
DATA_DIR="$WIKI_DIR/data/wiki"
EXPORT_DIR="$WIKI_DIR/export"

echo "Wiki.js quick setup script"

# Check for docker
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker not found. Install Docker first: https://docs.docker.com/engine/install/debian/"
  exit 1
fi

# Check for docker compose (v2)
if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose (v2) not available. Install docker compose plugin or use Docker Desktop."
  exit 1
fi

# Copy .env if present
if [ -f "$ENV_FILE_SRC" ]; then
  echo "Copying project .env to wiki folder..."
  cp -f "$ENV_FILE_SRC" "$ENV_FILE_DEST"
else
  echo "Warning: $ENV_FILE_SRC not found. You'll need to create $ENV_FILE_DEST with DB vars." 
  cat > "$ENV_FILE_DEST" <<'EOF'
# Example .env (replace values)
WIKI_DB_HOST=127.0.0.1
WIKI_DB_PORT=5432
WIKI_DB_USER=wikijs
WIKI_DB_PASS=changeme
WIKI_DB_NAME=wikijs
EOF
  echo "Created example .env at $ENV_FILE_DEST — edit values before proceeding."
fi

# Ensure data directories exist
mkdir -p "$DATA_DIR"
mkdir -p "$EXPORT_DIR"

# Make data dir writable
chmod -R 755 "$WIKI_DIR/data"

# Start Wiki.js
echo "Starting Wiki.js with docker compose (using $ENV_FILE_DEST)..."
docker compose --env-file "$ENV_FILE_DEST" up -d

# Wait and show logs
echo "Waiting 5 seconds for startup..."
sleep 5

echo "Tailing logs (ctrl-C to stop). If you see 'Please visit / and finish setup' the service is running." 

docker compose logs --no-color --follow wikijs

# End
