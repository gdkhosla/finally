#!/usr/bin/env bash
# Stop and remove the FinAlly container. The data volume is preserved.
set -euo pipefail

CONTAINER="finally"

if docker container inspect "${CONTAINER}" &>/dev/null; then
  echo "Stopping container '${CONTAINER}'..."
  docker rm -f "${CONTAINER}"
  echo "Container stopped. Data volume 'finally-data' is intact."
else
  echo "Container '${CONTAINER}' is not running."
fi
