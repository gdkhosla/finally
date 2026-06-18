"""Runtime configuration read from environment variables."""
import os

STATIC_DIR = os.environ.get("FINALLY_STATIC_DIR", "/app/static")
SNAPSHOT_INTERVAL_SECONDS = 30
