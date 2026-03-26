#!/usr/bin/env bash
# Deploy local: buildea el frontend y reinicia los servicios de producción local.
# Uso: ./deploy_local.sh
# Corré esto cuando quieras "publicar" cambios al entorno local de producción.

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
# En worktrees, el venv puede vivir en el proyecto principal
if [ ! -d "$VENV_DIR" ]; then
  MAIN_PROJECT_VENV="$(dirname "$(git -C "$ROOT_DIR" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)")/.venv"
  if [ -d "$MAIN_PROJECT_VENV" ]; then
    VENV_DIR="$MAIN_PROJECT_VENV"
  fi
fi

echo ""
echo "🚀 Deploy local de admin-consumos"
echo "=================================="

# --- 1. Detener instancia actual ---
echo ""
echo "⏹  Deteniendo instancia actual..."
bash "$ROOT_DIR/stop_prod.sh"

# --- 2. Instalar dependencias del backend ---
echo ""
echo "🐍 Actualizando dependencias backend..."
source "$VENV_DIR/bin/activate"
pip install -q -r "$ROOT_DIR/backend/requirements.txt"

# --- 3. Build del frontend ---
echo ""
echo "⚛️  Buildeando frontend..."
cd "$ROOT_DIR/frontend"
npm install --silent
npm run build

# --- 4. Iniciar servicios ---
echo ""
echo "▶️  Iniciando servicios..."
bash "$ROOT_DIR/start_prod.sh"

echo ""
echo "✅ Deploy completado."
echo "   Frontend: http://localhost:4173"
echo "   Backend:  http://localhost:8080"
