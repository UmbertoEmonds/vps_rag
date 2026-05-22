#!/usr/bin/env bash
# Injects netem-style latency on packets going to the postgres container,
# via pumba (https://github.com/alexei-led/pumba). No modification of the
# student's compose file or code required.
#
# Usage: ./inject.sh [DURATION] [DELAY_MS] [JITTER_MS] [TARGET]
# Example: ./inject.sh 5m 500 100 simplon_rag_postgres_pgvector
set -euo pipefail

DURATION="${1:-5m}"
DELAY_MS="${2:-500}"
JITTER_MS="${3:-100}"
TARGET="${4:-simplon_rag_postgres_pgvector}"

if ! docker ps --format '{{.Names}}' | grep -q "^${TARGET}\$"; then
  echo "Target container '${TARGET}' is not running." >&2
  exit 1
fi

if docker ps -a --format '{{.Names}}' | grep -q '^simplon_rag_postgres_replica$'; then
  echo "Removing previous chaos container..."
  docker rm -f simplon_rag_postgres_replica >/dev/null
fi

echo "Injecting ${DELAY_MS}ms ± ${JITTER_MS}ms latency on '${TARGET}' for ${DURATION}..."
docker run -d \
  --name simplon_rag_postgres_replica \
  -v /var/run/docker.sock:/var/run/docker.sock \
  gaiaadm/pumba \
  netem \
  --duration "${DURATION}" \
  delay \
  --time "${DELAY_MS}" \
  --jitter "${JITTER_MS}" \
  "${TARGET}" >/dev/null

echo "Done. Tail with: docker logs -f simplon_rag_postgres_replica"
echo "Revert manually with: ./revert.sh  (or wait ${DURATION})"
