# Admin Consumos 💳

Admin Consumos es una aplicación web de uso local diseñada para gestionar gastos de tarjetas de crédito con seguimiento de cuotas. Es una herramienta hogareña, sin autenticación, enfocada en la simplicidad y la privacidad de los datos.

## 🚀 Características Principales

- **Seguimiento de Cuotas**: Gestión automática de consumos en cuotas, permitiendo ver el impacto en meses futuros.
- **Importación Inteligente**: Soporte para importar resúmenes bancarios:
  - Visa XLSX.
  - PDFs de resúmenes (Banco Nación Visa/Mastercard, MercadoPago).
  - Detección automática de cuotas ("x de y") y fechas de cierre.
- **División de Gastos y Fondo Común**: El sistema implementa una lógica de pozo compartido donde los ingresos se promedian para cubrir gastos comunes, asegurando que a ambos participantes les quede el mismo dinero disponible al final del mes.
- **Reportes Mensuales**: Visualización del desglose de gastos por mes, categorías y personas, incluyendo el cálculo exacto de transferencias necesarias para equilibrar el pozo común.
- **Conversión de Moneda**: Soporte para consumos en USD con carga manual de cotizaciones mensuales para reportes precisos en ARS.
- **Deduplicación**: Sistema basado en huellas digitales (SHA256) para evitar importar el mismo consumo dos veces.

## 🛡️ Privacidad y Seguridad

- **Totalmente Local**: Tus datos nunca salen de tu computadora. El procesamiento de archivos se realiza en memoria/directorios temporales locales.
- **Sin Nube**: No hay servidores externos, bases de datos remotas ni trackers.
- **Ignorado Automático**: El proyecto incluye un `.gitignore` configurado para evitar que tus resúmenes (`resumenes/`) y tu base de datos (`data/`) se suban accidentalmente a la nube si usas Git.

## 🏗️ Arquitectura

El proyecto está organizado como un monorepositorio con backend y frontend independientes:

- **Backend**: FastAPI (Python 3.11+) con SQLModel (SQLAlchemy + Pydantic) y SQLite.
- **Frontend**: React + TypeScript + Vite, utilizando `@tanstack/react-query` para la gestión de estado y CSS puro para el diseño.

## 🛠️ Instalación y Uso

### Requisitos Previos
- Python 3.11 o superior.
- Node.js y npm.

### Arranque Rápido
La forma más sencilla de iniciar la aplicación es utilizando el script de arranque:

```bash
./start.sh
```

Este script se encarga de crear el entorno virtual, instalar las dependencias de backend y frontend, e iniciar ambos servidores en paralelo.

- **Frontend**: `http://localhost:5173`
- **Backend (API)**: `http://localhost:8000`
- **Base de Datos**: Se crea automáticamente en `data/app.db`.

## 💻 Desarrollo

Si prefieres ejecutar los componentes por separado:

### Backend
```bash
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
cd backend && uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## 🎨 Diseño
La aplicación utiliza un sistema de diseño minimalista con una paleta de colores cálidos (Terracotta, Crema, Marrón oscuro) definida en `index.css` de forma nativa, buscando una experiencia placentera y limpia.

## 🗺️ Roadmap
- [ ] Simulador de compras (What-if?) para prever impacto de nuevas cuotas.
- [ ] Categorización automática basada en historial.
- [ ] Proyección de flujo de caja (Cash Flow).
- [ ] Exportación de resúmenes para compartir por WhatsApp.
- [ ] Alertas de fechas de cierre y vencimiento.

---
*Desarrollado como una herramienta personal para el control de finanzas domésticas.*
