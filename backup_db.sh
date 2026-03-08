#!/usr/bin/env bash
# Backup diario de la base de datos SQLite
# Guarda hasta 30 backups rotando los más viejos
# Ejecutado diariamente por launchd

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="$ROOT_DIR/backups"
DB_PATH="${DB_PATH:-$ROOT_DIR/data/app.db}"
LOG_DIR="$HOME/Library/Logs/admin-consumos"
BACKUP_LOG="$LOG_DIR/backup.log"
MAX_BACKUPS=30

mkdir -p "$BACKUP_DIR" "$LOG_DIR"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$BACKUP_LOG"
}

# Verificar que la DB existe
if [ ! -f "$DB_PATH" ]; then
  log "ERROR: No se encontró la base de datos en $DB_PATH"
  exit 1
fi

TIMESTAMP=$(date '+%Y-%m-%d_%H-%M-%S')
BACKUP_FILE="$BACKUP_DIR/app_${TIMESTAMP}.db"

# Usar SQLite .backup para una copia consistente (segura incluso si la DB está en uso)
if command -v sqlite3 &> /dev/null; then
  sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"
  log "Backup creado con sqlite3 (copia consistente): $BACKUP_FILE"
else
  cp "$DB_PATH" "$BACKUP_FILE"
  log "Backup creado con cp: $BACKUP_FILE"
fi

# Rotación: mantener solo los últimos MAX_BACKUPS backups
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/app_*.db 2>/dev/null | wc -l | tr -d ' ')
if [ "$BACKUP_COUNT" -gt "$MAX_BACKUPS" ]; then
  TO_DELETE=$(( BACKUP_COUNT - MAX_BACKUPS ))
  ls -1t "$BACKUP_DIR"/app_*.db | tail -"$TO_DELETE" | xargs rm -f
  log "Rotación: eliminados $TO_DELETE backups antiguos (quedan $MAX_BACKUPS)"
fi

SIZE=$(du -sh "$BACKUP_FILE" | cut -f1)
log "OK - Tamaño: $SIZE | Total backups: $(ls -1 "$BACKUP_DIR"/app_*.db | wc -l | tr -d ' ')"
