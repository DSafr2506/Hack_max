#!/usr/bin/env bash
# Снимок SQLite без остановки. Запускать из папки проекта; в cron:
# 0 3 * * * cd /opt/max-app && ./deploy/backup.sh >> backups/backup.log 2>&1
set -euo pipefail
mkdir -p backups
STAMP=$(date +%Y%m%d-%H%M%S)
docker compose exec -T backend python -c "
import sqlite3; src = sqlite3.connect('/data/app.db'); dst = sqlite3.connect('/data/backup.db'); src.backup(dst); dst.close()"
docker compose cp backend:/data/backup.db "backups/app-$STAMP.db"
ls -1t backups/app-*.db | tail -n +15 | xargs -r rm --   # храним 14 последних
echo "OK backups/app-$STAMP.db"
