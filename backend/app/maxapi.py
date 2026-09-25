"""Интеграция с MAX: проверка initData мини-приложения, клиент Bot API, long polling.

Документация: https://dev.max.ru/docs/webapps/validation, https://dev.max.ru/docs-api
"""

import hashlib
import hmac
import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit

import httpx

from app.config import settings
from app.tls import ca_bundle

log = logging.getLogger("app.maxapi")

MAX_TEXT_LIMIT = 4000
CALLBACK_PAYLOAD_LIMIT = 256
PER_DIALOG_INTERVAL = 0.5  # лимит MAX: 2 сообщения в секунду в один диалог
POLL_TIMEOUT = 25  # сек. Сервер держит соединение до 30 с (лимит с 11.05.2026)


# ─────────────────────────── initData ───────────────────────────


class AuthError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def extract_web_app_data(raw: str) -> str:
    """Принимает либо строку initData (window.WebApp.initData), либо полный URL
    запуска / фрагмент вида `WebAppData=...&WebAppPlatform=...`, и возвращает initData."""
    raw = raw.strip()
    if "#" in raw:
        raw = urlsplit(raw).fragment or raw.split("#", 1)[1]
    if raw.startswith("WebAppData="):
        for key, value in parse_qsl(raw, keep_blank_values=True):
            if key == "WebAppData":
                return value
    return raw


def sign_init_data(params: dict[str, str], bot_token: str) -> str:
    """Подпись набора параметров тем же алгоритмом, что у MAX. Нужна для тестов и dev-стенда."""
    launch_params = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    return hmac.new(secret_key, launch_params.encode(), hashlib.sha256).hexdigest()


def verify_init_data(
    init_data: str,
    bot_token: str,
    now: datetime | None = None,
    ttl: timedelta | None = None,
) -> dict[str, Any]:
    """Проверяет подпись initData. Возвращает только то, что нам нужно; профиль MAX не отдаёт."""
    if not bot_token:
        raise AuthError("max_bot_token_missing")
    init_data = extract_web_app_data(init_data)
    if not init_data:
        raise AuthError("max_init_data_malformed")

    pairs = [p.split("=", 1) for p in init_data.split("&") if p]
    if any(len(p) != 2 for p in pairs):
        raise AuthError("max_init_data_malformed")

    hashes = [v for k, v in pairs if k == "hash"]
    if len(hashes) != 1:
        raise AuthError("max_init_data_hash_invalid")
    received = unquote(hashes[0]).lower()

    decoded = sorted(((k, unquote(v)) for k, v in pairs if k != "hash"), key=lambda kv: kv[0])
    launch_params = "\n".join(f"{k}={v}" for k, v in decoded)

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret_key, launch_params.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated, received):
        raise AuthError("max_init_data_signature_mismatch")

    data = dict(decoded)
    try:
        auth_date = datetime.fromtimestamp(int(data["auth_date"]), tz=timezone.utc)
        user = json.loads(data["user"])
        external_id = str(int(user["id"]))
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        raise AuthError("max_init_data_malformed") from None

    now = now or datetime.now(timezone.utc)
    ttl = ttl or timedelta(seconds=settings.max_auth_ttl_seconds)
    if now - auth_date > ttl:
        raise AuthError("max_init_data_expired")

    return {
        "external_id": external_id,  # только это и сохраняем
        "start_param": data.get("start_param") or None,
        "query_id": data.get("query_id"),
        "auth_date": auth_date,
    }


# ─────────────────────────── кнопки ───────────────────────────


def btn_callback(text: str, payload: str, intent: str = "default") -> dict[str, Any]:
    if len(payload) > CALLBACK_PAYLOAD_LIMIT:
        raise ValueError("callback payload длиннее 256 символов")
    return {"type": "callback", "text": text, "payload": payload, "intent": intent}


def btn_link(text: str, url: str) -> dict[str, Any]:
    return {"type": "link", "text": text, "url": url}


def btn_open_app(text: str, payload: str | None = None) -> dict[str, Any]:
    """Кнопка, открывающая наше мини-приложение. payload придёт в initData как start_param."""
    button: dict[str, Any] = {"type": "open_app", "text": text}
    if settings.max_bot_name:
        button["web_app"] = settings.max_bot_name
    elif BOT_INFO.get("user_id"):
        button["contact_id"] = BOT_INFO["user_id"]
    if payload:
        button["payload"] = payload
    return button


def keyboard(rows: list[list[dict[str, Any]]]) -> dict[str, Any]:
    rows = [row for row in rows if row]
    return {"type": "inline_keyboard", "payload": {"buttons": rows}}


# ─────────────────────────── клиент Bot API ───────────────────────────


BOT_INFO: dict[str, Any] = {}  # заполняется из GET /me при старте


@dataclass
class SendResult:
    ok: bool
    status: int = 0
    error: str | None = None
    message_id: str | None = None


class MaxClient:
    """Синхронный клиент MAX Bot API. Токен — в заголовке Authorization, без Bearer."""

    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        verify: str | bool = ca_bundle()
        self._http = httpx.Client(
            base_url=base_url or settings.max_api_base,
            headers={"Authorization": token if token is not None else settings.max_bot_token},
            timeout=httpx.Timeout(10.0, read=POLL_TIMEOUT + 10),
            verify=verify,
            transport=transport,
        )
        self._sleep = sleep
        self._last_sent: dict[str, float] = {}
        self._lock = threading.Lock()

    def close(self) -> None:
        self._http.close()

    # — служебное —

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response | None:
        for attempt in range(3):
            try:
                resp = self._http.request(method, path, **kwargs)
            except httpx.HTTPError as exc:
                log.warning("MAX %s %s: сетевая ошибка %s: %s", method, path, type(exc).__name__, exc)
                if attempt == 2:
                    return None
                self._sleep(1.0 * (attempt + 1))
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                log.warning("MAX %s %s: %s, повтор", method, path, resp.status_code)
                if attempt == 2:
                    return resp
                self._sleep(1.0 * (attempt + 1))
                continue
            return resp
        return None

    def _throttle(self, user_id: str) -> None:
        with self._lock:
            last = self._last_sent.get(user_id)
            now = time.monotonic()
            if last is not None and now - last < PER_DIALOG_INTERVAL:
                self._sleep(PER_DIALOG_INTERVAL - (now - last))
            self._last_sent[user_id] = time.monotonic()

    @staticmethod
    def _error_of(resp: httpx.Response | None) -> str:
        if resp is None:
            return "network_error"
        try:
            body = resp.json()
            return str(body.get("code") or body.get("message") or resp.status_code)
        except ValueError:
            return str(resp.status_code)

    # — методы API —

    def get_me(self) -> dict[str, Any] | None:
        resp = self._request("GET", "/me")
        if resp is None or resp.status_code != 200:
            log.error("MAX GET /me не удался: %s", self._error_of(resp))
            return None
        return resp.json()

    def send_message(
        self,
        user_id: str | int,
        text: str,
        buttons: list[list[dict[str, Any]]] | None = None,
        notify: bool = True,
    ) -> SendResult:
        uid = str(user_id)
        body: dict[str, Any] = {"text": text[:MAX_TEXT_LIMIT], "format": "markdown", "notify": notify}
        if buttons:
            body["attachments"] = [keyboard(buttons)]
        self._throttle(uid)
        resp = self._request("POST", "/messages", params={"user_id": int(uid)}, json=body)

        # Кнопка-ссылка на localhost/невалидный URL даёт 400 — лучше дойти без кнопок, чем не дойти.
        if resp is not None and resp.status_code == 400 and buttons:
            log.warning("MAX отклонил сообщение с кнопками (%s), шлём без них", self._error_of(resp))
            body.pop("attachments")
            resp = self._request("POST", "/messages", params={"user_id": int(uid)}, json=body)

        if resp is None or resp.status_code != 200:
            return SendResult(False, resp.status_code if resp is not None else 0, self._error_of(resp))
        mid = (resp.json().get("message") or {}).get("body", {}).get("mid")
        return SendResult(True, 200, message_id=mid)

    def answer_callback(
        self,
        callback_id: str,
        notification: str | None = None,
        new_text: str | None = None,
        keep_buttons: bool = False,
    ) -> bool:
        """POST /answers. Ответить нужно обязательно, иначе у пользователя крутится кнопка.
        new_text заменяет текст исходного сообщения; кнопки при этом снимаются."""
        body: dict[str, Any] = {}
        if notification:
            body["notification"] = notification
        if new_text is not None:
            message: dict[str, Any] = {"text": new_text[:MAX_TEXT_LIMIT], "format": "markdown"}
            if not keep_buttons:
                message["attachments"] = []
            body["message"] = message
        resp = self._request("POST", "/answers", params={"callback_id": callback_id}, json=body)
        ok = resp is not None and resp.status_code == 200 and resp.json().get("success", True)
        if not ok:
            log.warning("MAX POST /answers не удался: %s", self._error_of(resp))
        return bool(ok)

    def get_updates(
        self, marker: int | None, timeout: int = POLL_TIMEOUT, limit: int = 100
    ) -> tuple[list[dict[str, Any]], int | None] | None:
        params: dict[str, Any] = {"timeout": timeout, "limit": limit}
        if marker is not None:
            params["marker"] = marker
        try:
            resp = self._http.get("/updates", params=params)
        except httpx.HTTPError as exc:
            log.warning("MAX GET /updates: %s: %s", type(exc).__name__, exc)
            return None
        if resp.status_code != 200:
            log.warning("MAX GET /updates: %s %s", resp.status_code, self._error_of(resp))
            return None
        data = resp.json()
        return data.get("updates") or [], data.get("marker")

    def list_subscriptions(self) -> list[str]:
        resp = self._request("GET", "/subscriptions")
        if resp is None or resp.status_code != 200:
            return []
        return [s.get("url", "") for s in resp.json().get("subscriptions", [])]

    def subscribe_webhook(self, url: str, secret: str, update_types: list[str] | None = None) -> bool:
        body: dict[str, Any] = {"url": url}
        if secret:
            body["secret"] = secret
        if update_types:
            body["update_types"] = update_types
        resp = self._request("POST", "/subscriptions", json=body)
        ok = resp is not None and resp.status_code == 200 and resp.json().get("success", True)
        if not ok:
            log.error("MAX: подписка на вебхук не удалась: %s", self._error_of(resp))
        return bool(ok)

    def drop_webhooks(self) -> int:
        """Long polling не работает, пока у бота есть подписка на вебхук. Снимаем все."""
        dropped = 0
        for url in self.list_subscriptions():
            resp = self._request("DELETE", "/subscriptions", params={"url": url})
            if resp is not None and resp.status_code == 200:
                dropped += 1
        if dropped:
            log.info("MAX: снято подписок на вебхук: %s", dropped)
        return dropped


_client: MaxClient | None = None


def get_client() -> MaxClient:
    global _client
    if _client is None:
        _client = MaxClient()
    return _client


def set_client(client: MaxClient | None) -> None:
    """Для тестов: подменить клиент."""
    global _client
    _client = client


def send_message(
    user_id: str, text: str, buttons: list[list[dict[str, Any]]] | None = None, notify: bool = True
) -> bool:
    return get_client().send_message(user_id, text, buttons, notify).ok


# ─────────────────────────── разбор обновлений ───────────────────────────


def update_user_id(update: dict[str, Any]) -> str | None:
    """Достаёт user_id из любого типа обновления. Остальной профиль не трогаем."""
    candidates = [
        (update.get("callback") or {}).get("user", {}).get("user_id"),
        (update.get("user") or {}).get("user_id"),
        update.get("user_id"),
        ((update.get("message") or {}).get("sender") or {}).get("user_id"),
    ]
    for value in candidates:
        if value is not None:
            return str(value)
    return None


_PII_KEYS = {"first_name", "last_name", "name", "username", "avatar_url", "full_avatar_url", "description", "photo_url"}


def scrub(obj: Any) -> Any:
    """Убирает из апдейта персональные поля — для логов и фикстур."""
    if isinstance(obj, dict):
        return {k: ("***" if k in _PII_KEYS else scrub(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    return obj


def dump_fixture(update: dict[str, Any], directory: str = "tests/fixtures") -> None:
    """Первое реальное обновление каждого типа сохраняем (без ПДн) — по нему пишутся тесты."""
    kind = update.get("update_type", "unknown")
    path = Path(directory) / f"real_{kind}.json"
    if path.exists():
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(scrub(update), ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("MAX: записана фикстура %s", path)
    except OSError:
        log.warning("MAX: не удалось записать фикстуру %s", path)


# ─────────────────────────── long polling ───────────────────────────


class Poller(threading.Thread):
    """Фоновый поток: GET /updates в режиме long polling, маркер хранится в БД."""

    def __init__(self, client: MaxClient, handler: Callable[[dict[str, Any]], None]) -> None:
        super().__init__(name="max-poller", daemon=True)
        self.client = client
        self.handler = handler
        self.stop_event = threading.Event()

    def stop(self) -> None:
        self.stop_event.set()

    def run(self) -> None:
        from app import logic

        marker = logic.load_marker()
        log.info("MAX polling запущен, marker=%s", marker)
        backoff = 1.0
        while not self.stop_event.is_set():
            result = self.client.get_updates(marker)
            if result is None:
                self.stop_event.wait(backoff)
                backoff = min(backoff * 2, 30.0)
                continue
            backoff = 1.0
            updates, new_marker = result
            for update in updates:
                try:
                    self.handler(update)
                except Exception:
                    log.exception("MAX: ошибка обработки %s", update.get("update_type"))
            if new_marker is not None and new_marker != marker:
                marker = new_marker
                logic.save_marker(marker)
            if not updates:
                self.stop_event.wait(0.5)  # не больше 2 RPS на /updates


WEBHOOK_PATH = "/max/webhook"
WEBHOOK_UPDATE_TYPES = [
    "bot_started",
    "bot_stopped",
    "dialog_removed",
    "dialog_muted",
    "dialog_unmuted",
    "message_created",
    "message_callback",
]


def webhook_url() -> str:
    return settings.public_url.rstrip("/") + WEBHOOK_PATH


def ensure_webhook() -> bool:
    """Сторож подписки: MAX отписывает бота после 8 часов неуспешных доставок.
    Вызывается при старте и планировщиком раз в 30 минут."""
    if not settings.max_bot_token or settings.max_mode != "webhook":
        return False
    client = get_client()
    url = webhook_url()
    if url in client.list_subscriptions():
        return True
    log.warning("MAX: подписки на %s нет, подписываемся", url)
    return client.subscribe_webhook(url, settings.max_webhook_secret, WEBHOOK_UPDATE_TYPES)


def check_webhook_secret(header_value: str | None) -> bool:
    if not settings.max_webhook_secret:
        return True
    return hmac.compare_digest(header_value or "", settings.max_webhook_secret)


def start_bot(handler: Callable[[dict[str, Any]], None]) -> Poller | None:
    if not settings.max_bot_token:
        log.warning("MAX_BOT_TOKEN не задан — бот не запущен")
        return None
    client = get_client()
    me = client.get_me()
    if me:
        BOT_INFO.update({"user_id": me.get("user_id"), "username": me.get("username")})
        if not settings.max_bot_name and me.get("username"):
            settings.max_bot_name = me["username"]
        log.info("MAX: бот %s (id %s)", me.get("username"), me.get("user_id"))
    if settings.max_mode == "webhook":
        ensure_webhook()
        return None
    if not settings.max_polling_enabled:
        return None
    if settings.max_drop_webhooks:
        client.drop_webhooks()
    poller = Poller(client, handler)
    poller.start()
    return poller


# ─────────────────────────── CLI для ручной проверки ───────────────────────────
#   python -m app.maxapi me                  — кто я (GET /me) и активные вебхуки
#   python -m app.maxapi send <user_id>      — тестовое сообщение с кнопками
#   python -m app.maxapi poll                — вывести приходящие апдейты (без ПДн) и сохранить фикстуры
#   python -m app.maxapi initdata <user_id>  — подписанная initData для curl (только локально!)


def _cli() -> None:
    import sys

    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    args = sys.argv[1:]
    client = get_client()
    if not args or args[0] == "me":
        me = client.get_me() or {}
        # профиль бота — не персональные данные, username нужен для MAX_BOT_NAME
        print(json.dumps({**scrub(me), "username": me.get("username")}, ensure_ascii=False, indent=2))  # noqa: T201
        print("webhooks:", client.list_subscriptions())  # noqa: T201
    elif args[0] == "send" and len(args) == 2:
        me = client.get_me() or {}
        BOT_INFO.update({"user_id": me.get("user_id"), "username": me.get("username")})
        rows = [
            [btn_open_app("Открыть приложение")],
            [btn_callback("Проверка callback", "ping")],
        ]
        print(client.send_message(args[1], "Проверка связи с ботом **MAX**", rows))  # noqa: T201
    elif args[0] == "poll":
        client.drop_webhooks()
        marker = None
        while True:
            result = client.get_updates(marker)
            if result is None:
                time.sleep(2)
                continue
            updates, marker = result
            for u in updates:
                print(json.dumps(scrub(u), ensure_ascii=False, indent=2))  # noqa: T201
                dump_fixture(u)
                cb = u.get("callback") or {}
                if cb.get("callback_id"):
                    client.answer_callback(cb["callback_id"], "pong")
    elif args[0] == "initdata" and len(args) == 2:
        from urllib.parse import quote

        params = {
            "auth_date": str(int(time.time())),
            "query_id": "dev",
            "user": json.dumps({"id": int(args[1])}),
        }
        h = sign_init_data(params, settings.max_bot_token)
        print("&".join(f"{k}={quote(v)}" for k, v in params.items()) + f"&hash={h}")  # noqa: T201
    else:
        print(_cli.__doc__ or "см. комментарий над _cli")  # noqa: T201


if __name__ == "__main__":
    _cli()
