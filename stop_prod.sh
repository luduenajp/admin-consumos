#!/usr/bin/env bash
# Detiene la instancia de producción local
# Uso: ./stop_prod.sh

PID_FILE="/tmp/admin_consumos_prod.pid"

if [ ! -f "$PID_FILE" ]; then
  echo "[admin-consumos] No hay instancia corriendo (PID file no encontrado)."
  exit 0
fi

PIDS=$(cat "$PID_FILE")
echo "[admin-consumos] Deteniendo procesos ($PIDS)..."
kill $PIDS 2>/dev/null && echo "[admin-consumos] Detenido." || echo "[admin-consumos] Algunos procesos ya estaban detenidos."
rm -f "$PID_FILE"
