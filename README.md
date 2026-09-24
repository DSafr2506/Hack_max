# Hack_max — «Агрегатор возможностей» в MAX

Мини-приложение для школьников внутри мессенджера MAX: онбординг → подборка олимпиад, смен, хакатонов и профпроб → «Участвую» → «Мои даты» → напоминание от бота о дедлайне.

```
frontend/            мини-приложение (React + Vite) — экраны, фильтры, карточки
backend/             API (FastAPI) + бот MAX + напоминания + каталог мероприятий
Dockerfile           общий образ: собирает фронт и кладёт его в бэкенд — один контейнер
deploy/              Caddy (HTTPS на сервере), бэкап и обновление
docker-compose.yml   запуск одной командой
```

## Запуск одной командой (Docker)

Нужен Docker: на Windows — [Docker Desktop](https://www.docker.com/products/docker-desktop/), на сервере — `curl -fsSL https://get.docker.com | sh`.

```bash
cp .env.example .env        # Windows: copy .env.example .env
# в .env вписать MAX_BOT_TOKEN, поменять JWT_SECRET и ADMIN_TOKEN
docker compose up -d --build
```

Откройте http://localhost:8080 (порт меняется в `.env`, `HTTP_PORT`). Всё работает в одном контейнере `app`: фронт, API, бот и напоминания. При первом запуске бэкенд сам создаст базу и загрузит мероприятия из `backend/data/events.yaml`.

| Команда | Что делает |
|---|---|
| `docker compose logs -f app` | логи API и бота |
| `docker compose exec app python -m app.maxapi me` | проверить токен бота |
| `docker compose exec app python -m app.seed` | перечитать `events.yaml` после правок |
| `docker compose up -d --build` | пересобрать после изменений кода |
| `docker compose down` | остановить (база сохраняется в томе `app-data`) |

**Проверка в браузере без MAX.** Подборка и карточки открываются сразу. «Участвую», «Мои даты» и напоминания требуют входа, а он есть только внутри MAX. Для локальной проверки поставьте в `.env` `DEV_FAKE_AUTH=1`, выполните `docker compose up -d` и откройте http://localhost:8080/?dev=me&demo=1. `demo=1` добавляет в карточку «Демо-напоминание»: через ≤30 секунд бот напишет в MAX. Перед показом верните `DEV_FAKE_AUTH=0`.

**Внутри MAX** приложение открывается только по https с доменом. Выкат на сервер с доменом — [DEPLOY.md](DEPLOY.md).

## Как фронт связан с бэкендом

- `frontend/src/services/session.ts` — при запуске загружает справочники (`/api/dicts`: города и регионы) и выполняет вход через MAX (`initData` → `/api/auth/launch`).
- `frontend/src/services/opportunities.ts` — мероприятия из `/api/events?detail=full`. Фильтры, как и раньше, работают на фронте.
- `frontend/src/services/api.ts` — HTTP-клиент и перевод модели бэкенда в модель фронта (`types.ts`).
- Онбординг сохраняется на бэкенд (`/api/me/onboarding`): класс, город, типы и коды целей. Текст целей остаётся на устройстве, из него по ключевым словам выводятся коды целей.
- Карточка: «Участвую» (`/api/me/participations` → календарь и напоминания бота), «Перейти к регистрации» через `/go/{id}` (считаются переходы), «Поделиться», «В календарь» (.ics).
- Профиль: «Мои даты» (`/api/me/calendar`) и экспорт в календарь телефона.
- `frontend/src/integration/max.ts` — MAX Bridge: `initData`, системная кнопка «назад», `openLink`, `shareMaxContent`, `downloadFile`.
- Диплинки: `?startapp=e_<id>` (кнопка в напоминании бота) и `ev_<токен>` («Поделиться») сразу открывают нужную карточку.

Во фронте 4 типа мероприятий. Гранты, творческие конкурсы, волонтёрство и спорт из каталога бэкенда пока не показываются. Смены на бэкенде называются `camp`, во фронте — `school`.

Разработка без Docker: [backend/README.md](backend/README.md) и [frontend/README.md](frontend/README.md).
