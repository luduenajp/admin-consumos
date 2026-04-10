#!/usr/bin/env bash
# Detiene la instancia de producción local
# Uso: ./stop_prod.sh

PID_FILE="/tmp/admin_consumos_prod.pid"
BACKEND_PORT=8080
FRONTEND_PORT=4173

# 1) Matar por PID file (proceso padre + sus hijos directos)
if [ -f "$PID_FILE" ]; then
  PIDS=$(cat "$PID_FILE")
  echo "[admin-consumos] Deteniendo procesos del PID file ($PIDS)..."
  for PID in $PIDS; do
    # Matar el proceso y todos sus hijos
    pkill -TERM -P "$PID" 2>/dev/null
    kill "$PID" 2>/dev/null
  done
  rm -f "$PID_FILE"
else
  echo "[admin-consumos] PID file no encontrado, buscando por puerto..."
fi

# 2) Fallback: matar cualquier proceso que siga escuchando en los puertos de prod
sleep 1
for PORT in $BACKEND_PORT $FRONTEND_PORT; do
  PORT_PIDS=$(lsof -ti :"$PORT" 2>/dev/null)
  if [ -n "$PORT_PIDS" ]; then
    echo "[admin-consumos] Matando procesos en puerto $PORT: $PORT_PIDS"
    echo "$PORT_PIDS" | xargs kill -TERM 2>/dev/null
  fi
done

echo "[admin-consumos] Detenido."
