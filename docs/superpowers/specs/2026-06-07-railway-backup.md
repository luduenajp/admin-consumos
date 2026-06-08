# Railway DB Backup — Spec

**Date:** 2026-06-07  
**Status:** Approved

## Objetivo

Descargar semanalmente la base de datos SQLite del volumen de Railway a la Mac local, con autenticación por token y ejecución resiliente ante apagados de la máquina.

## Arquitectura

```
Railway (FastAPI)                     Mac local
─────────────────                     ─────────────────────────────────────
GET /api/backup/db        ──────►     backup_railway.sh
  Auth: Bearer <token>                  ├─ verifica timestamp (.last_backup)
  Response: app.db stream               ├─ curl → backups/railway/app_DATE.db
                                        ├─ valida SQLite header
                                        ├─ rota (max 30 archivos)
                                        └─ actualiza .last_backup

                                      com.adminconsumos.backup-railway.plist
                                        └─ RunAtLoad: true → llama al script
```

## Backend — Endpoint `/api/backup/db`

**Archivo:** `backend/app/api.py`

- Método: `GET /api/backup/db`
- Auth: header `Authorization: Bearer <BACKUP_TOKEN>` comparado con `secrets.compare_digest` contra env var `BACKUP_TOKEN`
- Si `BACKUP_TOKEN` no está definida en el entorno → responde 503 (backup deshabilitado)
- Si el token no coincide → responde 401
- Proceso:
  1. Crea archivo temporal `/tmp/backup_TIMESTAMP.db`
  2. Usa `sqlite3.connect(...).backup(...)` (Python stdlib) para copia consistente
  3. Streamea el archivo como `StreamingResponse` con `Content-Disposition: attachment; filename=app_YYYY-MM-DD.db`
  4. Borra el archivo temporal en un bloque `finally`
- No requiere sesión de DB del pool — abre conexión directa al archivo

## Script local — `backup_railway.sh`

**Variables de entorno requeridas** (leídas desde `~/.adminconsumos-backup.env`):
- `RAILWAY_APP_URL` — URL base de la app en Railway (ej: `https://admin-consumos.up.railway.app`)
- `BACKUP_TOKEN` — token secreto

**Lógica:**
1. Sourcea `~/.adminconsumos-backup.env` si existe
2. Lee `backups/railway/.last_backup` (epoch timestamp)
3. Si pasaron menos de 7 días → exit 0 (no es momento aún)
4. Llama `curl -f -H "Authorization: Bearer $BACKUP_TOKEN" $RAILWAY_APP_URL/api/backup/db -o <archivo_tmp>`
5. Verifica que el archivo comience con el magic bytes de SQLite (`SQLite format 3`)
6. Mueve el archivo a `backups/railway/app_YYYY-MM-DD_HH-MM-SS.db`
7. Actualiza `backups/railway/.last_backup` con el epoch actual
8. Rotación: elimina archivos `app_*.db` más viejos si hay más de 30
9. Loguea en `~/Library/Logs/admin-consumos/backup_railway.log`

## launchd — `com.adminconsumos.backup-railway.plist`

```xml
<key>RunAtLoad</key><true/>
```

- Se instala en `~/Library/LaunchAgents/`
- `RunAtLoad: true` → corre el script en cada login/boot
- El script decide internamente si es momento de hacer backup (via timestamp)
- Comportamiento ante apagado: si la Mac estaba apagada el día programado, el backup corre al próximo arranque

## Archivos creados/modificados

| Archivo | Acción |
|---|---|
| `backend/app/api.py` | Nuevo endpoint `GET /api/backup/db` |
| `backup_railway.sh` | Nuevo script de backup |
| `com.adminconsumos.backup-railway.plist` | Nuevo launchd job |
| `backups/railway/.gitkeep` | Nuevo directorio en repo |

## Configuración manual (una sola vez)

### En Railway
```
BACKUP_TOKEN=<output de: openssl rand -hex 32>
```

### En la Mac
```bash
# Crear ~/.adminconsumos-backup.env
echo 'RAILWAY_APP_URL=https://tu-app.up.railway.app' >> ~/.adminconsumos-backup.env
echo 'BACKUP_TOKEN=<mismo token>' >> ~/.adminconsumos-backup.env
chmod 600 ~/.adminconsumos-backup.env

# Registrar el launchd job
cp com.adminconsumos.backup-railway.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.adminconsumos.backup-railway.plist
```

## Seguridad

- `BACKUP_TOKEN` nunca va al repositorio
- Comparación con `secrets.compare_digest` (no vulnerable a timing attacks)
- `~/.adminconsumos-backup.env` con permisos `600`
- Sin `BACKUP_TOKEN` en Railway → endpoint deshabilitado (503)

## Out of scope

- Backup a nube (Google Drive, S3)
- Backup de la instancia local (ya existe `backup_db.sh`)
- Notificaciones de fallo de backup
