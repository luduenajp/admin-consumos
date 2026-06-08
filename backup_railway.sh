#!/bin/bash
set -euo pipefail

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="$SCRIPT_DIR/backups/railway"
LAST_BACKUP_FILE="$BACKUP_DIR/.last_backup"
LOG_DIR="$HOME/Library/Logs/admin-consumos"
LOG_FILE="$LOG_DIR/backup_railway.log"
TMP_FILE="/tmp/backup_railway_tmp.db"

# ── Cleanup trap ─────────────────────────────────────────────────────────────
trap 'rm -f "$TMP_FILE"' EXIT

# ── Logging ──────────────────────────────────────────────────────────────────
mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# ── Load env ─────────────────────────────────────────────────────────────────
ENV_FILE="$HOME/.adminconsumos-backup.env"
if [[ -f "$ENV_FILE" ]]; then
    # shellcheck source=/dev/null
    source "$ENV_FILE"
fi

# ── Validate required vars ────────────────────────────────────────────────────
if [[ -z "${RAILWAY_APP_URL:-}" ]]; then
    log "ERROR: RAILWAY_APP_URL is not set. Check $ENV_FILE"
    exit 1
fi
if [[ -z "${BACKUP_TOKEN:-}" ]]; then
    log "ERROR: BACKUP_TOKEN is not set. Check $ENV_FILE"
    exit 1
fi

# ── Check if 7 days have passed ───────────────────────────────────────────────
INTERVAL=604800  # 7 days in seconds

last_backup=0
if [[ -f "$LAST_BACKUP_FILE" ]] && [[ -s "$LAST_BACKUP_FILE" ]]; then
    last_backup=$(cat "$LAST_BACKUP_FILE")
fi

now=$(date +%s)
elapsed=$(( now - last_backup ))

if (( elapsed < INTERVAL )); then
    remaining=$(( INTERVAL - elapsed ))
    log "Skipping backup: only ${elapsed}s since last backup (need ${INTERVAL}s). Next backup in ${remaining}s."
    exit 0
fi

log "Starting Railway DB backup..."

# ── Create backup directory ───────────────────────────────────────────────────
mkdir -p "$BACKUP_DIR"

# ── Download DB ───────────────────────────────────────────────────────────────
log "Downloading DB from $RAILWAY_APP_URL/api/backup/db ..."
if ! curl -f -sS -H "Authorization: Bearer $BACKUP_TOKEN" \
    "$RAILWAY_APP_URL/api/backup/db" \
    -o "$TMP_FILE"; then
    log "ERROR: curl download failed."
    rm -f "$TMP_FILE"
    exit 1
fi

# ── Validate SQLite magic bytes ───────────────────────────────────────────────
# SQLite files start with "SQLite format 3\000" (16 bytes)
# Use 'file' command as primary check, fall back to xxd
MAGIC_OK=0
VALIDATOR_FOUND=0

if command -v file &>/dev/null; then
    VALIDATOR_FOUND=1
    if file "$TMP_FILE" | grep -q "SQLite"; then
        MAGIC_OK=1
    fi
fi

# Also verify with raw bytes as a secondary check
if [[ "$MAGIC_OK" -eq 0 ]]; then
    if command -v xxd &>/dev/null; then
        VALIDATOR_FOUND=1
        header=$(xxd -p -l 15 "$TMP_FILE" 2>/dev/null || true)
        # "SQLite format 3" in hex = 53514c69746520666f726d61742033
        if [[ "$header" == "53514c69746520666f726d61742033" ]]; then
            MAGIC_OK=1
        fi
    fi
fi

# Guard: if no validator is available, warn and exit
if [[ "$VALIDATOR_FOUND" -eq 0 ]]; then
    log "WARNING: Neither 'file' nor 'xxd' command available. Cannot validate SQLite magic bytes."
    exit 1
fi

if [[ "$MAGIC_OK" -eq 0 ]]; then
    log "ERROR: Downloaded file is not a valid SQLite database. Discarding."
    exit 1
fi

log "SQLite validation passed."

# ── Move to final destination ─────────────────────────────────────────────────
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
DEST="$BACKUP_DIR/app_${TIMESTAMP}.db"
mv "$TMP_FILE" "$DEST"
log "Backup saved to $DEST"

# ── Update last backup timestamp ──────────────────────────────────────────────
date +%s > "$LAST_BACKUP_FILE"

# ── Rotation: keep at most 30 backups ─────────────────────────────────────────
MAX_BACKUPS=30
# List files sorted alphabetically (oldest first because of YYYY-MM-DD format)
mapfile -t backup_files < <(find "$BACKUP_DIR" -maxdepth 1 -name "app_*.db" | sort)
count=${#backup_files[@]}

if (( count > MAX_BACKUPS )); then
    to_delete=$(( count - MAX_BACKUPS ))
    log "Rotating: $count backups found, deleting $to_delete oldest..."
    for (( i=0; i<to_delete; i++ )); do
        log "Deleting old backup: ${backup_files[$i]}"
        rm -f "${backup_files[$i]}"
    done
fi

log "Backup complete. Total backups: $(find "$BACKUP_DIR" -maxdepth 1 -name "app_*.db" | wc -l | tr -d ' ')"
