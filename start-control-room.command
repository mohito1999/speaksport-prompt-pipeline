#!/bin/zsh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

if [[ ! -x ".venv/bin/speaksport" ]]; then
  echo "SpeakSport setup is missing. Open Terminal in this folder and run:"
  echo ""
  echo "  uv sync --extra dev"
  echo ""
  read "?Press Return to close."
  exit 1
fi

echo "Starting SpeakSport Control Room…"
.venv/bin/speaksport ui &
SERVER_PID=$!

cleanup() {
  kill "$SERVER_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

for _ in {1..40}; do
  if curl --silent --fail http://127.0.0.1:8765/api/health >/dev/null 2>&1; then
    open http://127.0.0.1:8765/
    echo ""
    echo "Control Room is open. Keep this window running while you use it."
    echo "Press Control-C here when you are finished."
    wait "$SERVER_PID"
    exit $?
  fi
  sleep 0.25
done

echo "Control Room did not start. Check whether port 8765 is already in use."
exit 1
