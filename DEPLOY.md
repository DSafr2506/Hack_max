# Выкат на сервер (Docker)

Схема: один VPS, один домен, два контейнера.

```
Телефон (MAX) ──https──▶ ваш-домен ──▶ [caddy] ──┬─▶ фронт (статика внутри образа caddy)
                                                 └─▶ /api, /go, /health, /max/webhook ──▶ [backend] ──▶ SQLite в томе app-data
[backend] ──https──▶ platform-api2.max.ru (сообщения бота, приём событий)
```

Caddy сам получает и продлевает HTTPS-сертификат Let's Encrypt для домена. База лежит в Docker-томе `app-data` и переживает пересборку контейнеров. Мероприятия из `backend/data/events.yaml` загружаются сами при первом запуске.

## 0. Что нужно

| Что | Зачем |
|---|---|
| VPS: Ubuntu 22.04/24.04, 1 vCPU, 1–2 ГБ RAM, 20 ГБ диска, публичный IPv4. Лучше у российского хостера | Здесь работают контейнеры |
| Домен и A-запись `app.ваш-домен.ru → IP сервера` | MAX открывает мини-приложения только по https, вебхук — только на 443 |
| Токен бота | Уже есть |
| Организаторы хакатона | Только они могут вписать адрес мини-приложения в настройки бота (п. 6) |

Порты 80 и 443 должны быть открыты: Caddy получает сертификат через 80.

## 1. Репозиторий (на своём компьютере)

1. Сертификаты НУЦ Минцифры уже лежат в `backend/certs/` (`root.pem`, `sub.pem`) — образ соберётся, даже если сайт Госуслуг недоступен с сервера.
2. Отправьте ветку в репозиторий команды:

```bash
git push -u origin integration-backend
```

Проверка, что токен не попал в git: `git log --all -p | grep -i "MAX_BOT_TOKEN=."` — должно быть пусто.

## 2. Сервер: Docker (один раз, под root)

```bash
apt update && apt -y upgrade
curl -fsSL https://get.docker.com | sh          # Docker + compose-плагин
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable
```

Если `get.docker.com` не открывается, ставьте из репозитория Ubuntu: `apt -y install docker.io docker-compose-v2`.

**Docker Hub из России** часто отвечает отказом при скачивании образов (`python`, `node`, `caddy`). Тогда пропишите зеркало, которое даёт ваш хостер (у многих российских хостеров оно есть, адрес — в их документации):

```bash
cat > /etc/docker/daemon.json <<'JSON'
{ "registry-mirrors": ["https://<зеркало-вашего-хостера>"] }
JSON
systemctl restart docker
```

## 3. Код и настройки

```bash
git clone -b integration-backend https://github.com/DSafr2506/Hack_max.git /opt/max-app
cd /opt/max-app
cp .env.example .env && chmod 600 .env
nano .env
```

Что вписать в `.env`:

```ini
DOMAIN=app.ваш-домен.ru
PUBLIC_URL=https://app.ваш-домен.ru
FRONTEND_ORIGIN=https://app.ваш-домен.ru
ENV=prod
JWT_SECRET=<openssl rand -base64 48>
ADMIN_TOKEN=<openssl rand -base64 32>
MAX_BOT_TOKEN=<токен бота>
MAX_BOT_NAME=t829_hakaton_max_bot
MAX_MODE=polling
DEV_FAKE_AUTH=0
```

`MAX_CA_BUNDLE` оставьте как в примере: бандл собирается в образе.

## 4. Запуск

```bash
docker compose up -d --build                           # первая сборка — 3–5 минут
docker compose exec backend python -m app.maxapi me    # бот отвечает? имя бота видно?
curl -s https://app.ваш-домен.ru/health                # {"status":"ok","events":38,"bot":"t829_hakaton_max_bot"}
```

Логи: `docker compose logs -f backend` (приложение) и `docker compose logs -f caddy` (сертификат, входящие запросы).

## 5. Проверка в браузере

Откройте `https://app.ваш-домен.ru/` — откроется онбординг и подборка; «Участвую» и напоминания работают только внутри MAX (там есть вход). Проверить их из браузера можно так: временно `DEV_FAKE_AUTH=1`, `docker compose up -d`, открыть `https://app.ваш-домен.ru/?dev=test` и **сразу вернуть `DEV_FAKE_AUTH=0`**.

## 6. Привязать мини-приложение к боту (делают организаторы)

Отправьте организаторам:

> Пожалуйста, укажите в настройках бота `t829_hakaton_max_bot` ссылку на мини-приложение: `https://app.ваш-домен.ru/` (платформа MAX для партнёров → Чат-боты → бот → ⋮ → Настройки).

Требования MAX к адресу: только `https://`, латиница, цифры, точка и дефис, без пробелов, до 1024 символов.

## 7. Вебхук вместо long polling (по желанию)

Long polling работает и на сервере, для хакатона его достаточно. Для постоянной работы MAX рекомендует вебхук:

```ini
MAX_MODE=webhook
MAX_WEBHOOK_SECRET=<openssl rand -hex 24>
```

Затем `docker compose up -d`. Бэкенд сам подпишется на `https://app.ваш-домен.ru/max/webhook` и раз в 30 минут будет проверять, что подписка жива. Проверка: `docker compose exec backend python -m app.maxapi me` — в `webhooks` должен быть ваш адрес. Если организаторы против вебхуков, оставьте `polling`.

## 8. Приёмка на телефоне

1. Бот → «Старт» → пришло приветствие с кнопкой «Открыть подборку».
2. Кнопка открывает приложение → онбординг: класс, город, интересы, цели.
3. Лента с фильтром «Доступно из моего региона», карточка, «Участвую» → событие в «Моих датах».
4. На карточке нажать «Перейти к регистрации» → открывается сайт организатора.
5. Демо-напоминание: откройте приложение по ссылке `https://max.ru/t829_hakaton_max_bot?startapp=demo` — в карточке появится «Демо-напоминание», через ≤30 секунд придёт сообщение от бота.
6. Цифры для питча: `curl -s -H "X-Admin-Token: <ADMIN_TOKEN>" https://app.ваш-домен.ru/api/admin/stats`.

## 9. Бэкапы

```bash
crontab -e
# 0 3 * * * cd /opt/max-app && ./deploy/backup.sh >> backups/backup.log 2>&1
```

Снимки базы — в `/opt/max-app/backups`, хранятся 14 последних. Восстановление:

```bash
docker compose stop backend
docker compose cp backups/app-<дата>.db backend:/data/app.db
docker compose start backend
```

## 10. Обновление и откат

```bash
# у себя
git commit -am "…" && git tag v0.2 && git push --follow-tags
# на сервере
cd /opt/max-app && ./deploy/update.sh v0.2
```

`update.sh` делает бэкап, пересобирает контейнеры и ждёт `/health`. Если сервис не поднялся, он откатывается на прошлый коммит. Новые мероприятия: правите `backend/data/events.yaml` → коммит → `update.sh` → `docker compose exec backend python -m app.seed`.

## Чек-лист перед показом

- [ ] `DEV_FAKE_AUTH=0`
- [ ] `JWT_SECRET`, `ADMIN_TOKEN` (и `MAX_WEBHOOK_SECRET`, если вебхук) случайные; `.env` с правами 600 и не в git
- [ ] `https://домен/health` отвечает, `bot` не пустой
- [ ] Организаторы вписали адрес мини-приложения в настройки бота
- [ ] Приёмка из п. 8 пройдена на телефоне, который будет на сцене
- [ ] Даты в `backend/data/events.yaml` перепроверены
- [ ] Бэкап в cron, восстановление проверено один раз
