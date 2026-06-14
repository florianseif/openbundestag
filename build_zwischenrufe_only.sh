#!/usr/bin/env bash
set -e

REPO="/Users/jupiter/PycharmProjects/openbundestag"
DATA_DIR="$REPO/data"
DB="$REPO/openbundestag-data.db"
LOG="$REPO/build_zwischenrufe.log"

echo "[zw] Extracting zwischenrufe for all 21 terms → $DB" | tee "$LOG"
echo "[zw] $(date)" | tee -a "$LOG"

for TERM in $(seq 1 21); do
  echo "[zw] term $TERM …" | tee -a "$LOG"
  uv run run.py --phase zwischenrufe --term "$TERM" --db "$DB" --data-dir "$DATA_DIR" >> "$LOG" 2>&1
done

echo "[zw] Done! $(date)" | tee -a "$LOG"
