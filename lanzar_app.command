#!/bin/bash
# Ruta absoluta del proyecto para que funcione desde cualquier lugar
PROJECT_DIR="/Users/pablo/github/admin-consumos"

# Cambiar al directorio del proyecto
cd "$PROJECT_DIR" || exit

# Función para abrir el navegador después de un breve retraso
(sleep 5 && open http://localhost:5173) &

# Ejecutar el script de inicio
sh start.sh
