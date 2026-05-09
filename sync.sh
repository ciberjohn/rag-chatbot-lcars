#!/usr/bin/env bash
# Sync Google Drive folders to local docs directory.
# Set RCLONE_REMOTE to match your rclone remote name (run: rclone listremotes)
set -euo pipefail

RCLONE_REMOTE="${RCLONE_REMOTE:-drive}"
DOCS_DIR="${DOCS_DIR:-/opt/mytechbookswizzard/docs}"
LOG="${DOCS_DIR}/../rclone-sync.log"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] rclone sync starting" >> "$LOG"

rclone sync \
  "${RCLONE_REMOTE}:Documents/Tech Docs and Manuals" \
  "${DOCS_DIR}/" \
  --log-file="$LOG" --log-level INFO

rclone sync \
  "${RCLONE_REMOTE}:Documents/ebooks" \
  "${DOCS_DIR}/ebooks/" \
  --log-file="$LOG" --log-level INFO

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] rclone sync done" >> "$LOG"
