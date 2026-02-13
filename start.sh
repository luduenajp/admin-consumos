#!/usr/bin/env bash
# Start both backend and frontend dev servers
# Usage: ./start.sh

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cleanup() {
  echo ""
  echo -e "${YELLOW}Deteniendo servidores...${NC}"
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
  echo -e "${GREEN}Servidores detenidos.${NC}"
}

trap cleanup EXIT INT TERM

# --- Virtualenv check ---
if [ ! -d "$VENV_DIR" ]; then
  echo -e "${YELLOW}Creando virtualenv en $VENV_DIR ...${NC}"
  python3 -m venv "$VENV_DIR"
fi

echo -e "${GREEN}Activando virtualenv...${NC}"
source "$VENV_DIR/bin/activate"

# --- Backend deps ---
echo -e "${GREEN}Instalando dependencias del backend...${NC}"
pip install -q -r "$ROOT_DIR/backend/requirements.txt"

# --- Frontend deps ---
if [ ! -d "$ROOT_DIR/frontend/node_modules" ]; then
  echo -e "${GREEN}Instalando dependencias del frontend...${NC}"
  npm install --prefix "$ROOT_DIR/frontend"
fi

# --- Start backend ---
echo -e "${GREEN}Iniciando backend (http://localhost:8000) ...${NC}"
cd "$ROOT_DIR/backend"
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

# --- Start frontend ---
echo -e "${GREEN}Iniciando frontend (http://localhost:5173) ...${NC}"
cd "$ROOT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Backend:  http://localhost:8000${NC}"
echo -e "${GREEN}  Frontend: http://localhost:5173${NC}"
echo -e "${GREEN}  Presiona Ctrl+C para detener ambos${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

wait
