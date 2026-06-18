#!/usr/bin/env bash
# Start the FinAlly container. Pass --build to force a fresh image build.
set -euo pipefail

IMAGE="finally"
CONTAINER="finally"
VOLUME="finally-data"
PORT="8000"
URL="http://localhost:${PORT}"

BUILD=false
for arg in "$@"; do
  [[ "$arg" == "--build" ]] && BUILD=true
done

# Build if image doesn't exist or --build was requested
if $BUILD || ! docker image inspect "${IMAGE}" &>/dev/null; then
  echo "Building image '${IMAGE}'..."
  docker build -t "${IMAGE}" "$(dirname "$0")/.."
fi

# Remove any stopped container with the same name
if docker container inspect "${CONTAINER}" &>/dev/null; then
  echo "Removing existing container '${CONTAINER}'..."
  docker rm -f "${CONTAINER}"
fi

echo "Starting container '${CONTAINER}'..."
docker run -d \
  --name "${CONTAINER}" \
  -v "${VOLUME}:/app/db" \
  -p "${PORT}:8000" \
  --env-file "$(dirname "$0")/../.env" \
  "${IMAGE}"

echo "FinAlly is running at ${URL}"

# Open browser if possible (macOS)
if command -v open &>/dev/null; then
  open "${URL}"
fi
