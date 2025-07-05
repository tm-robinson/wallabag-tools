#!/usr/bin/env bash
# run_jobs.sh
# Exit immediately if a command errors, propagate errors in pipes, fail on
# unset variables.
set -euo pipefail

###############################################################################
# 1.  Move to the directory that this wrapper lives in (important for cron).  #
###############################################################################
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

###############################################################################
# 2.  Export variables defined in .env so every Python script can read them.  #
###############################################################################
if [[ -f ".env" ]]; then
  # Temporarily auto-export everything we source.
  set -o allexport
  # shellcheck disable=SC1090 # (.env isn’t always in $PATH)
  source ".env"
  set +o allexport
else
  echo "[run_jobs] .env file not found in $SCRIPT_DIR" >&2
  exit 1
fi

###############################################################################
# 3.  Activate the virtual environment created with `python -m venv venv`.    #
###############################################################################
if [[ -f "venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "venv/bin/activate"
else
  echo "[run_jobs] venv not found at $SCRIPT_DIR/venv" >&2
  exit 1
fi

###############################################################################
# 4.  Run your scripts — stop immediately if the first one fails.             #
###############################################################################
python wallabag_rss_importer.py         # if this returns non-zero, set -e aborts the script
python wallabag_labeler.py

###############################################################################
# 5.  Deactivate venv (optional, mostly cosmetic in batch jobs).              #
###############################################################################
deactivate 2>/dev/null || true
