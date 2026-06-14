#!/usr/bin/env bash
# Daily runner for getMeMyLeads.
# Runs the scraper, copies today's CSV into results/, commits, and pushes.
# Designed to be called by systemd or cron. Logs everything to data/logs/.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TODAY=$(date +%Y-%m-%d)
LOG_DIR="${PROJECT_DIR}/data/logs"
LOG_FILE="${LOG_DIR}/daily_runner_${TODAY}.log"
EXPORT_FILE="${PROJECT_DIR}/data/exports/startup_signal_dump_${TODAY}.csv"
RESULT_FILE="${PROJECT_DIR}/results/startup_signal_dump_${TODAY}.csv"

mkdir -p "${LOG_DIR}" "${PROJECT_DIR}/results"

# Tee all output to both the log file and stdout (visible in journalctl)
exec > >(tee -a "${LOG_FILE}") 2>&1

log() { echo "[$(date '+%H:%M:%S')] $*"; }
fail() { log "ERROR: $*"; exit 1; }

log "============================================================"
log "Daily runner started: ${TODAY}"
log "Project dir: ${PROJECT_DIR}"
log "============================================================"

cd "${PROJECT_DIR}"

# ------------------------------------------------------------------ #
# Step 1: Run the scraper
# ------------------------------------------------------------------ #
log "Running scraper (app/main.py)..."
if ! python3 app/main.py; then
    fail "app/main.py exited with a non-zero status"
fi
log "Scraper finished."

# ------------------------------------------------------------------ #
# Step 2: Verify today's export was produced
# ------------------------------------------------------------------ #
if [[ ! -f "${EXPORT_FILE}" ]]; then
    fail "Expected export not found: ${EXPORT_FILE}"
fi
ROW_COUNT=$(( $(wc -l < "${EXPORT_FILE}") - 1 ))
log "Export verified: ${EXPORT_FILE} (${ROW_COUNT} records)"

# ------------------------------------------------------------------ #
# Step 3: Copy to results/ — skip if the file already exists
# (protects previous days from being overwritten on a re-run)
# ------------------------------------------------------------------ #
if [[ -f "${RESULT_FILE}" ]]; then
    log "Result file already exists — skipping copy: ${RESULT_FILE}"
else
    cp "${EXPORT_FILE}" "${RESULT_FILE}"
    log "Copied → ${RESULT_FILE}"
fi

# ------------------------------------------------------------------ #
# Step 4: Check whether there is anything new to commit
# ------------------------------------------------------------------ #
CHANGED=$(git -C "${PROJECT_DIR}" status --porcelain "results/startup_signal_dump_${TODAY}.csv" 2>/dev/null || true)
if [[ -z "${CHANGED}" ]]; then
    log "No new changes to commit. Already up to date."
    log "Done."
    exit 0
fi

# ------------------------------------------------------------------ #
# Step 5: Commit only today's result file
# ------------------------------------------------------------------ #
git -C "${PROJECT_DIR}" add "results/startup_signal_dump_${TODAY}.csv"
git -C "${PROJECT_DIR}" commit -m "Add startup signal dump ${TODAY}"
log "Committed: Add startup signal dump ${TODAY}"

# ------------------------------------------------------------------ #
# Step 6: Push to GitHub
# ------------------------------------------------------------------ #
if ! git -C "${PROJECT_DIR}" push origin main; then
    fail "git push failed — check SSH key and network"
fi
log "Pushed to origin/main."

log "============================================================"
log "Done. ${ROW_COUNT} records in results/startup_signal_dump_${TODAY}.csv"
log "============================================================"
