#!/usr/bin/env bash
# apply.sh — inject an incident on the student's clone, stealth-mode.
#
# - For patch-based incidents (01, 02, 03):
#     1. git apply the patch
#     2. mark every patched file with git update-index --skip-worktree
#        so `git status` and bare `git diff` stay clean
#     3. rebuild the api container
#
# - For incident 04, delegates to the pumba inject.sh.
#
# Usage:
#   ./incidents/apply.sh 01
#   ./incidents/apply.sh 04 10m 500 100
set -euo pipefail

NN="${1:?Usage: $0 <incident-number> [extra args for incident 04]}"
shift || true

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

  if ! git apply --check "$PATCH" 2>/dev/null; then
    echo "Patch does not apply cleanly. Trying --3way..." >&2
    git apply --3way "$PATCH"
  else
    git apply "$PATCH"
  fi

  # Extract patched file paths from "+++ b/..." headers
  FILES=$(grep -E "^\+\+\+ b/" "$PATCH" | sed 's|^+++ b/||')
  for f in $FILES; do
    git update-index --skip-worktree "$f"
  done

  docker compose up -d --build api >/dev/null
  echo "Incident $NN injected. Files hidden from 'git status':"
  for f in $FILES; do echo "  - $f"; done
else
  exec bash "$DIR/inject.sh" "$@"
fi
