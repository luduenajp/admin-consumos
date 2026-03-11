#!/usr/bin/env bash
# Script para iniciar Admin Consumos

echo "🚀 Iniciar Admin Consumos"
echo "========================="
echo ""

echo "📋 Opciones disponibles:"
echo ""

echo "1️⃣  Versión Productiva (recomendada):"
echo "   ./start_prod.sh"
echo "   - Frontend: http://www.consumofamiliar.com:4173"
echo "   - Backend:  http://www.consumofamiliar.com:8080"
echo "   - Más estable y rápida"
echo ""

echo "2️⃣  Versión Desarrollo:"
echo "   ./start.sh"
echo "   - Frontend: http://localhost:5173"
echo "   - Backend:  http://localhost:8000"
echo "   - Para desarrollo y testing"
echo ""

echo "3️⃣  Verificar estado actual:"
echo "   lsof -i :4173  # Frontend productivo"
echo "   lsof -i :8080  # Backend productivo"
echo "   lsof -i :5173  # Frontend desarrollo"
echo "   lsof -i :8000  # Backend desarrollo"
echo ""

echo "4️⃣  Si algo falla, reiniciar todo:"
echo "   ./stop_prod.sh && ./start_prod.sh"
echo ""

echo "🌐 URLs finales:"
echo "   Productivo: http://www.consumofamiliar.com:4173"
echo "   Desarrollo: http://localhost:5173"
