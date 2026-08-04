#!/usr/bin/env bash

set -u

PYTHON_BIN="${PYTHON_BIN:-python}"
RESTART_DELAY=5
STARTUP_FAIL_LIMIT=3
STARTUP_FAIL_WINDOW=15
rapid_failures=0

trap 'echo "[run.sh] Stop requested; exiting restart loop."; exit 0' INT TERM

while true; do
  start_time=$SECONDS
  "$PYTHON_BIN" bot.py
  exit_code=$?
  runtime=$((SECONDS - start_time))

  if [[ $exit_code -eq 0 ]]; then
    echo "[run.sh] bot.py exited cleanly; not restarting."
    exit 0
  fi

  if [[ $runtime -le $STARTUP_FAIL_WINDOW ]]; then
    rapid_failures=$((rapid_failures + 1))
  else
    rapid_failures=0
  fi

  if [[ $rapid_failures -ge $STARTUP_FAIL_LIMIT ]]; then
    echo "[run.sh] bot.py failed to stay up for ${STARTUP_FAIL_LIMIT} consecutive starts."
    echo "[run.sh] This usually means a fatal import/config/dependency problem; fix that before restarting."
    exit "$exit_code"
  fi

  echo "[run.sh] bot.py exited with code $exit_code; restarting in ${RESTART_DELAY}s."
  sleep "$RESTART_DELAY"

  if [[ $RESTART_DELAY -lt 60 ]]; then
    RESTART_DELAY=$((RESTART_DELAY * 2))
    if [[ $RESTART_DELAY -gt 60 ]]; then
      RESTART_DELAY=60
    fi
  fi
done