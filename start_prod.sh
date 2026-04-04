#!/usr/bin/env bash
# Inicia backend y frontend en modo "producción local"
# Backend: puerto 8080 | Frontend: puerto 4173 (vite preview)
# Uso: ./start_prod.sh

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
# En worktrees, el venv puede vivir en el proyecto principal (3 niveles arriba)
if [ ! -d "$VENV_DIR" ]; then
  MAIN_PROJECT_VENV="$(dirname "$(git -C "$ROOT_DIR" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)")/.venv"
  if [ -d "$MAIN_PROJECT_VENV" ]; then
    VENV_DIR="$MAIN_PROJECT_VENV"
  fi
fi
LOG_DIR="$HOME/Library/Logs/admin-consumos"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
PID_FILE="/tmp/admin_consumos_prod.pid"

BACKEND_PORT=8080
FRONTEND_PORT=4173

mkdir -p "$LOG_DIR"

# --- Verificar que no esté ya corriendo ---
if [ -f "$PID_FILE" ]; then
  PIDS=$(cat "$PID_FILE")
  if kill -0 $PIDS 2>/dev/null; then
    echo "[admin-consumos] Ya está corriendo (PIDs: $PIDS). Saliendo."
    exit 0
  fi
  rm -f "$PID_FILE"
fi

# --- Activar virtualenv ---
if [ ! -d "$VENV_DIR" ]; then
  echo "[admin-consumos] Virtualenv no encontrado en $VENV_DIR. Crearlo primero con: python3 -m venv .venv && pip install -r backend/requirements.txt"
  exit 1
fi
source "$VENV_DIR/bin/activate"

# --- Build del frontend si no existe ---
if [ ! -d "$ROOT_DIR/frontend/dist" ]; then
  echo "[admin-consumos] No se encontró el build del frontend. Buildeando..."
  cd "$ROOT_DIR/frontend"
  [ ! -d node_modules ] && npm install --silent
  npm run build
fi

# --- DB de producción (siempre del proyecto principal, no del worktree) ---
MAIN_PROJECT_ROOT="$(dirname "$(git -C "$ROOT_DIR" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)")"
export DB_PATH="$MAIN_PROJECT_ROOT/data/app.db"
echo "[admin-consumos] Usando DB de producción: $DB_PATH"

# --- Iniciar backend ---
echo "[admin-consumos] Iniciando backend en http://localhost:$BACKEND_PORT ..."
cd "$ROOT_DIR/backend"
nohup uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" \
  >> "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

# --- Esperar que el backend esté listo ---
echo "[admin-consumos] Esperando que el backend esté listo..."
for i in $(seq 1 20); do
  if curl -sf "http://localhost:$BACKEND_PORT/health" > /dev/null 2>&1; then
    echo "[admin-consumos] Backend listo."
    break
  fi
  sleep 1
done

# --- Iniciar frontend (vite preview) ---
echo "[admin-consumos] Iniciando frontend en http://localhost:$FRONTEND_PORT ..."
cd "$ROOT_DIR/frontend"
nohup env PATH="/usr/local/bin:$PATH" BACKEND_PORT=$BACKEND_PORT npx vite preview --port "$FRONTEND_PORT" --host 0.0.0.0 \
  >> "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

# --- Guardar PIDs ---
echo "$BACKEND_PID $FRONTEND_PID" > "$PID_FILE"

echo "[admin-consumos] Iniciado."
echo "  Backend:  http://localhost:$BACKEND_PORT"
echo "  Frontend: http://localhost:$FRONTEND_PORT"
echo "  PIDs guardados en: $PID_FILE"
echo "  Logs: $LOG_DIR"
