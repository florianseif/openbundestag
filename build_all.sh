#!/usr/bin/env bash
# Build the full openbundestag DB with zwischenrufe for all 21 terms.
# Run from the repo root: bash build_all.sh
set -e

DB="openbundestag-data.db"
LOG="build_all.log"

echo "[build] Starting full pipeline → $DB" | tee "$LOG"
echo "[build] $(date)" | tee -a "$LOG"

# Phase 1: transform + load all terms
for TERM in $(seq 1 21); do
  echo "[build] transform+load term $TERM …" | tee -a "$LOG"
  uv run run.py --phase load --term "$TERM" --db "$DB" >> "$LOG" 2>&1
done

# Phase 2: ministers (once, replaces table)
echo "[build] ministers …" | tee -a "$LOG"
uv run run.py --phase ministers --db "$DB" >> "$LOG" 2>&1

# Phase 3: finalize (once, materialises derived columns)
echo "[build] finalize …" | tee -a "$LOG"
uv run run.py --phase finalize --db "$DB" >> "$LOG" 2>&1

# Phase 4: zwischenrufe all terms
for TERM in $(seq 1 21); do
  echo "[build] zwischenrufe term $TERM …" | tee -a "$LOG"
  uv run run.py --phase zwischenrufe --term "$TERM" --db "$DB" >> "$LOG" 2>&1
done

echo "[build] Done! $(date)" | tee -a "$LOG"
