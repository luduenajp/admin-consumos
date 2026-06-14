#!/usr/bin/env bash
# Smoke-test: verifica que los endpoints clave responden bien en una instancia corriendo.
# Uso:
#   ./scripts/smoke_test.sh                      # contra http://localhost:8000
#   BASE_URL=https://miapp.up.railway.app ./scripts/smoke_test.sh
#
# Si la instancia tiene Basic Auth, exportá las credenciales:
#   APP_USERNAME=pablo APP_PASSWORD=secreto ./scripts/smoke_test.sh
#
# Sale con código 0 si todos los checks pasan; 1 si alguno falla.

set -uo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
APP_USERNAME="${APP_USERNAME:-}"
APP_PASSWORD="${APP_PASSWORD:-}"
YM="$(date +%Y-%m)"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'

AUTH_ARGS=()
if [ -n "$APP_USERNAME" ] && [ -n "$APP_PASSWORD" ]; then
  AUTH_ARGS=(-u "$APP_USERNAME:$APP_PASSWORD")
fi

pass=0; fail=0

# check <method> <path> <expected_status> [extra curl args...]
check() {
  local method="$1" path="$2" expected="$3"; shift 3
  local code
  code=$(curl -s -o /dev/null -w '%{http_code}' -X "$method" \
    --max-time 15 ${AUTH_ARGS[@]+"${AUTH_ARGS[@]}"} "$@" "$BASE_URL$path" 2>/dev/null)
  if [ "$code" = "$expected" ]; then
    echo -e "  ${GREEN}✓${NC} $method $path → $code"
    pass=$((pass + 1))
  else
    echo -e "  ${RED}✗${NC} $method $path → $code (esperado $expected)"
    fail=$((fail + 1))
  fi
}

echo -e "${YELLOW}Smoke-test contra $BASE_URL (mes $YM)${NC}"
echo ""

# Público (sin auth)
check GET  "/health"                                  200

# Lecturas clave (con auth si está configurada)
check GET  "/api/people"                              200
check GET  "/api/cards"                               200
check GET  "/api/categories"                          200
check GET  "/api/purchases?page=1&page_size=1"        200
check GET  "/api/reports/month-breakdown?year_month=$YM" 200
check GET  "/api/reports/timeline"                    200
check GET  "/api/savings"                             200
check GET  "/api/goals"                               200

echo ""
if [ "$fail" -eq 0 ]; then
  echo -e "${GREEN}✓ Todo OK: $pass checks pasaron.${NC}"
  exit 0
else
  echo -e "${RED}✗ $fail check(s) fallaron, $pass pasaron.${NC}"
  exit 1
fi
