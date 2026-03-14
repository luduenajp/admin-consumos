#!/usr/bin/env bash
# Watchdog: verifica si backend y frontend están corriendo.
# Si alguno no responde, reinicia start_prod.sh.
# Ejecutado cada 15 minutos por launchd.

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$HOME/Library/Logs/admin-consumos"
WATCHDOG_LOG="$LOG_DIR/watchdog.log"
BACKEND_PORT=8080
FRONTEND_PORT=4173

mkdir -p "$LOG_DIR"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$WATCHDOG_LOG"
}

check_port() {
  curl -sf --max-time 3 "http://localhost:$1" > /dev/null 2>&1
}

BACKEND_OK=false
FRONTEND_OK=false

# Verificar backend (endpoint /health)
if curl -sf --max-time 3 "http://localhost:$BACKEND_PORT/health" > /dev/null 2>&1; then
  BACKEND_OK=true
fi

# Verificar frontend
if check_port "$FRONTEND_PORT"; then
  FRONTEND_OK=true
fi

if $BACKEND_OK && $FRONTEND_OK; then
  log "OK - Backend y frontend corriendo."
  exit 0
fi

# Algo no está corriendo
if ! $BACKEND_OK; then
  log "ALERTA - Backend no responde en puerto $BACKEND_PORT."
fi
if ! $FRONTEND_OK; then
  log "ALERTA - Frontend no responde en puerto $FRONTEND_PORT."
fi

log "Intentando reiniciar con start_prod.sh..."

# Limpiar PID file para forzar el reinicio
rm -f /tmp/admin_consumos_prod.pid

bash "$ROOT_DIR/start_prod.sh" >> "$WATCHDOG_LOG" 2>&1
log "Reinicio completado."
