#!/usr/bin/env bash
# Stops the pumba chaos container. Network latency is removed immediately
# (netem rules are tied to the pumba process lifecycle).
set -euo pipefail

if docker ps --format '{{.Names}}' | grep -q '^simplon_rag_postgres_replica$'; then
  echo "Stopping chaos container..."
  docker rm -f simplon_rag_postgres_replica >/dev/null
  echo "Done."
else
  echo "No active chaos container."
fi
