#!/usr/bin/env bash
# Script para ver logs de la aplicación

echo "📋 Logs de Admin Consumos"
echo "========================"
echo ""

echo "🌐 Logs Frontend (puerto 4173):"
echo "   tail -f ~/Library/Logs/admin-consumos/frontend.log"
echo ""

echo "🔧 Logs Backend (puerto 8080):"
echo "   tail -f ~/Library/Logs/admin-consumos/backend.log"
echo ""

echo "📋 Logs de startup:"
echo "   tail -f ~/Library/Logs/admin-consumos/startup.log"
echo ""

echo "🔍 Ver todos los logs disponibles:"
echo "   ls -la ~/Library/Logs/admin-consumos/"
echo ""

echo "📊 Ver si los servicios están corriendo:"
echo "   brew services list | grep dnsmasq"
echo "   lsof -i :4173  # Frontend"
echo "   lsof -i :8080  # Backend"
echo ""

echo "🔄 Reiniciar servicios si es necesario:"
echo "   ./stop_prod.sh && ./start_prod.sh"
