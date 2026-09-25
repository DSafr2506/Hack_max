"""LLM через OpenRouter (OpenAI-совместимый API). По умолчанию — DeepSeek.

Только извлечение данных из текста страниц в JSON, никаких решений о публикации.
Проверка связи: python -m app.llm
"""

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger("app.llm")


class LLMError(Exception):
    pass


class LLMParseError(LLMError):
    """Модель ответила, но не JSON-объектом. Повторять запрос бессмысленно — нужен переспрос с ошибкой."""

    def __init__(self, message: str, raw: str, tokens_in: int = 0, tokens_out: int = 0, cost: float | None = None):
        super().__init__(message)
        self.raw, self.tokens_in, self.tokens_out, self.cost = raw, tokens_in, tokens_out, cost


@dataclass
class LLMResult:
    data: dict[str, Any]
    raw: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float | None


_client: httpx.Client | None = None


def _http() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            base_url=settings.llm_api_base.rstrip("/"),
            timeout=settings.llm_timeout,
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "HTTP-Referer": settings.public_url,
                "X-Title": "Agregator vozmozhnostey",
            },
        )
    return _client


def set_transport(transport: httpx.BaseTransport | None) -> None:
    """Для тестов: подменить HTTP-транспорт."""
    global _client
    _client = None if transport is None else httpx.Client(base_url="https://llm.test/api/v1", transport=transport)


def parse_json(text: str) -> dict[str, Any]:
    """Снимает ```json-ограждения и достаёт первый JSON-объект из ответа."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            raise LLMError("в ответе нет JSON")
        text = text[start : end + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"невалидный JSON: {exc}") from None
    if not isinstance(data, dict):
        raise LLMError("ожидался JSON-объект")
    return data


def chat_json(messages: list[dict[str, str]], model: str | None = None, retries: int = 2) -> LLMResult:
    if not settings.llm_api_key and _client is None:
        raise LLMError("LLM_API_KEY не задан")
    model = model or settings.llm_model
    body = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "usage": {"include": True},
    }
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = _http().post("/chat/completions", json=body)
            if resp.status_code in (429, 500, 502, 503, 504):
                raise LLMError(f"HTTP {resp.status_code}")
            if resp.status_code != 200:
                raise LLMError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            payload = resp.json()
            if "error" in payload:
                raise LLMError(str(payload["error"])[:300])
            content = payload["choices"][0]["message"]["content"] or ""
            usage = payload.get("usage") or {}
            try:
                data = parse_json(content)
            except LLMError as exc:
                raise LLMParseError(
                    str(exc),
                    content,
                    int(usage.get("prompt_tokens") or 0),
                    int(usage.get("completion_tokens") or 0),
                    usage.get("cost"),
                ) from None
            result = LLMResult(
                data=data,
                raw=content,
                model=payload.get("model", model),
                tokens_in=int(usage.get("prompt_tokens") or 0),
                tokens_out=int(usage.get("completion_tokens") or 0),
                cost_usd=usage.get("cost"),
            )
            log.info(
                "LLM %s: %s→%s токенов, $%s", result.model, result.tokens_in, result.tokens_out, result.cost_usd
            )
            return result
        except LLMParseError:
            raise
        except (httpx.HTTPError, LLMError, KeyError, ValueError) as exc:
            last = exc
            log.warning("LLM попытка %s: %s", attempt + 1, exc)
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
    raise LLMError(str(last))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    r = chat_json(
        [
            {"role": "system", "content": "Отвечай только JSON."},
            {"role": "user", "content": 'Верни {"ok": true, "model": "<твоё название>"}'},
        ]
    )
    print(json.dumps({"answer": r.data, "model": r.model, "tokens": [r.tokens_in, r.tokens_out], "cost_usd": r.cost_usd}, ensure_ascii=False))  # noqa: T201
