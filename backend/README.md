# Бэкенд — мини-приложение «Агрегатор возможностей» в MAX

Весь проект поднимается из корня репозитория через `docker compose` — см. [../README.md](../README.md). Ниже — устройство бэкенда и запуск без Docker.

Навигатор олимпиад, смен, хакатонов и профпроб для школьников внутри MAX: онбординг → подборка с фильтрами → «Участвую» → «Мои даты» → напоминание от бота.

```
app/          FastAPI: вход через MAX, каталог, участие, календарь, напоминания, бот, модерация
data/         справочники, города, мероприятия (events.yaml) — загружаются при первом запуске сами
certs/        сертификаты НУЦ Минцифры (root.pem, sub.pem) для запросов к API MAX
tests/        pytest: подпись MAX, фильтры, сквозной сценарий, каталог, бот
prompts/      промпт извлечения (extract_v1.txt)
scripts/      demo_flow.py — сквозная проверка с настоящим ботом без фронта
```

## Локальный запуск (Windows, без Docker)

Настройки — один файл `.env` в корне проекта (рядом с `docker-compose.yml`), бэкенд читает его сам. Сертификаты НУЦ для API MAX берутся из `backend/certs/` автоматически.

Бэкенд (первый терминал):

```bat
cd C:\Users\Ег\projects\hack-max
copy .env.example .env          :: если .env ещё нет; вписать MAX_BOT_TOKEN, для отладки в браузере DEV_FAKE_AUTH=1
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

База без Docker — `backend/app.db`.

Фронт (второй терминал, из папки `frontend` в корне репозитория): `npm ci && npm run dev`, затем http://127.0.0.1:5173/?dev=me — вход под тестовым пользователем (нужен `DEV_FAKE_AUTH=1`). `&demo=1` включает демо-режим: кнопку «Демо-напоминание» в карточке.

Тесты: `pytest -q && ruff check .`

При старте бэкенд:
1. вызывает `GET /me` и пишет в лог имя бота;
2. в режиме `MAX_MODE=polling` снимает вебхуки и запускает long polling (`GET /updates`, маркер в таблице `bot_state`); в режиме `webhook` подписывается на `PUBLIC_URL/max/webhook`;
3. запускает APScheduler: раз в 30 с рассылает созревшие напоминания.

## Ручная проверка бота (сделать в первый час)

```bash
python -m app.maxapi me                 # токен рабочий? есть ли вебхуки?
python -m app.maxapi poll               # нажать «Старт» в боте → в консоли появится апдейт с вашим user_id
python -m app.maxapi send <user_id>     # придёт сообщение с кнопками «Открыть приложение» и «Проверка callback»
python -m app.maxapi initdata <user_id> # подписанная initData для curl (только локально)
```

`poll` сохраняет первое реальное событие каждого типа в `tests/fixtures/real_<тип>.json`, **с вырезанными именами**. Сверьте `real_message_callback.json` с модельной `message_callback.json` (пункт 11.2 записки) и при расхождении поправьте `update_user_id` / `handle_callback`.

## Что реализовано

| Что | Где |
|---|---|
| Проверка подписи `initData` по алгоритму dev.max.ru, TTL 1 час. Принимает и строку `WebApp.initData`, и полный URL с `#WebAppData=…` | `maxapi.verify_init_data` |
| Из профиля MAX берётся только `user.id` | `verify_init_data`, `logic.launch_user` |
| Клиент Bot API: `Authorization: <token>` без Bearer, домен `platform-api2.max.ru`, повтор при 429/5xx, 2 сообщения в секунду на диалог | `maxapi.MaxClient` |
| Если MAX не принял кнопку (например, ссылка на `localhost`), сообщение уходит без кнопок, чтобы не потерять напоминание | `MaxClient.send_message` |
| Кнопки `callback`, `link`, `open_app` (с `payload` → `start_param`) | `btn_*` |
| Ответ на нажатие через `POST /answers`; у followup после ответа кнопки снимаются | `MaxClient.answer_callback` |
| `bot_started` и `/start` включают уведомления и шлют приветствие, `bot_stopped` и `dialog_removed` выключают и гасят очередь, `dialog_muted` → `notify:false` | `logic._handle_update` |
| Ответ 403/404 при отправке (бот заблокирован) тоже выключает уведомления | `logic.dispatch_reminders` |
| Тихие часы 22:00–08:00 МСК (кроме демо), до 3 попыток отправки | `logic.dispatch_reminders` |
| Диплинк `https://max.ru/<bot>?startapp=ev_<22 символа base64url>`, `share_url` вида `https://max.ru/:share?text=…`, `signups` считаются только у новых пользователей | `logic`, `GET /api/events/{slug}/share` |

### Callback-payload (≤256 символов)

| payload | действие |
|---|---|
| `fu:<event_id>:participated` / `fu:<event_id>:skipped` | ответ на followup → статус участия |
| `snz:<reminder_id>` | «Напомнить завтра» |
| `stale:<event_id>` | «Информация устарела» → `freshness=reported` |

### `start_param`, которые получает фронт

- `ev_…`, `col_…`, `cls_…` — токены шеринга (бэкенд сам засчитает `signups`);
- `e_<event_id>` — открыть карточку (кнопка «Открыть карточку» в напоминании).

`POST /api/auth/launch` возвращает `start_param`, чтобы фронт мог сразу открыть нужный экран.

## Эндпоинты

```
GET   /api/dicts                  справочники: типы, цели, предметы, регионы, города
GET   /api/events?goals=&types=&grade=&region_code=&available_from_region=&price_kinds=&only_with_deadline=&q=&sort=&limit=&offset=
GET   /api/events/{slug}          карточка с блоками trust и action     GET /api/events/{slug}/similar
GET   /api/events/{slug}.ics      GET /api/events/{slug}/calendar-links  GET /api/me/calendar.ics?token=
GET   /api/events/by-id/{id}      для диплинка e_<id>
GET   /api/admin/events?stale_days=&freshness=reported   POST /api/admin/events/{id}/verify|archive
GET   /api/admin/stats            цифры для питча (заголовок X-Admin-Token)
GET   /api/admin/candidates?status=new   GET|PATCH /api/admin/candidates/{id}
POST  /api/admin/candidates/{id}/approve|reject   POST /api/admin/pipeline/run   GET /api/admin/quality
GET   /admin                      экран модерации
POST  /api/auth/launch            {"init_data": "<window.WebApp.initData>"} → {token, user, is_new, start_param}
GET   /api/me          PATCH /api/me          POST /api/me/onboarding   {grade, city, type_codes, goal_codes}
GET   /api/me/participations?status=
POST  /api/me/participations      {event_id, status="going"}   идемпотентно; going → календарь + напоминания
PATCH /api/me/participations/{id} {status}
GET   /api/me/calendar?from=&to=
GET   /go/{event_id}?src=feed|card|reminder|share   302 на сайт организатора + Click
POST  /api/demo/fire-reminder     {event_id, delay_seconds=10}
GET   /api/events/{slug}/share    POST /api/share/{token}/open
```

Демо на сцене:

```bash
TOKEN=$(curl -s -XPOST localhost:8000/api/auth/launch -H 'content-type: application/json' \
  -d "{\"init_data\":\"$(python -m app.maxapi initdata <ваш_user_id>)\"}" | jq -r .token)
curl -s -XPOST localhost:8000/api/demo/fire-reminder -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -d '{"event_id":1,"delay_seconds":0}'
# через ≤30 секунд в MAX придёт напоминание
```

## Важно перед демо

- `PUBLIC_URL` должен быть публичным https-адресом. Иначе MAX не примет кнопку-ссылку `/go/…`, и напоминание придёт без неё.
- Если MAX не проходит проверку TLS, соберите бандл certifi + сертификаты НУЦ Минцифры и укажите его в `MAX_CA_BUNDLE` (в Docker-образе это сделано автоматически). Проверку не отключать.
- Мероприятия: `data/events.yaml`, 38 записей, проверены 24.09.2026. Перед показом перепроверьте даты и выполните `python -m app.seed`.
- Прод: `MAX_MODE=webhook`, пошагово — в [DEPLOY.md](DEPLOY.md). Вебхук `POST /max/webhook` проверяет заголовок `X-Max-Bot-Api-Secret`, отвечает 200 сразу и обрабатывает событие в фоне; сторож раз в 30 минут восстанавливает подписку.
- Long polling (режим разработки) держит соединение 25 с, а не опрашивает каждые 3–5 с: с 11.05.2026 у `/updates` лимит 2 RPS, таймаут 30 с, TTL событий 24 часа.
- Логгер `httpx` приглушён: в URL запросов есть `user_id`. `init_data` и токены не логируются.
- `DEV_FAKE_AUTH=0` на демо (есть тест).
