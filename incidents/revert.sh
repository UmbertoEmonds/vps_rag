#!/usr/bin/env bash
# revert.sh — undo a previously injected incident.
#
# For patch-based incidents:
#   1. clear the skip-worktree flag on each patched file
#   2. git checkout the file back to HEAD
#   3. rebuild the api container
#
# For incident 04, delegates to the pumba revert.sh.
#
# Usage:
#   ./incidents/revert.sh 01
set -euo pipefail

NN="${1:?Usage: $0 <incident-number>}"

cd "$(git rev-parse --show-toplevel)"

case "$NN" in
  01) DIR="incidents/01-evaluator-loop"; KIND=patch ;;
  02) DIR="incidents/02-slow-retrieval"; KIND=patch ;;
  03) DIR="incidents/03-prompt-hallucination"; KIND=patch ;;
  04) DIR="incidents/04-pg-network-latency"; KIND=script ;;
  05) DIR="incidents/05-runaway-chunking"; KIND=patch ;;
  *) echo "Unknown incident: $NN" >&2; exit 1 ;;
esac

if [ "$KIND" = "patch" ]; then
  PATCH="$DIR/incident.patch"
  FILES=$(grep -E "^\+\+\+ b/" "$PATCH" | sed 's|^+++ b/||')

  for f in $FILES; do
    git update-index --no-skip-worktree "$f" 2>/dev/null || true
    git checkout -- "$f"
  done

  docker compose up -d --build api >/dev/null
  echo "Incident $NN reverted."
else
  exec bash "$DIR/revert.sh"
fi
