#!/usr/bin/env bash
# Обновление на сервере: ./deploy/update.sh [ветка или тег]
set -euo pipefail
REF="${1:-integration-backend}"
PREV=$(git rev-parse HEAD)
git fetch --all --tags --prune
git checkout -q "$REF"
git pull -q --ff-only origin "$REF" 2>/dev/null || true
./deploy/backup.sh || echo "бэкап не сделан (первый запуск?)"
docker compose up -d --build
for i in $(seq 1 20); do
  if docker compose exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" 2>/dev/null; then
    echo "OK: $(git rev-parse --short HEAD)"; exit 0
  fi
  sleep 3
done
echo "health не ответил — откат на $PREV" >&2
git checkout -q "$PREV"
docker compose up -d --build
exit 1
