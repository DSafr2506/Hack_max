# Всё приложение в одном образе: собранный фронт + API + бот MAX + напоминания.
# Сборка и запуск:  docker compose up -d --build   (или docker build -t hack-max . && docker run -p 8080:8000 --env-file .env hack-max)

# ── 1. фронт ──
FROM node:22-alpine AS front
WORKDIR /front
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ── 2. бэкенд, который заодно раздаёт фронт ──
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install -r requirements.txt

# Сертификаты НУЦ Минцифры: API MAX подписан ими, а httpx доверяет только certifi.
# Лежат в backend/certs/; если их нет — пробуем скачать при сборке.
COPY backend/certs/ /tmp/certs/
RUN python - <<'PY'
import certifi, pathlib, urllib.request
certs = pathlib.Path("/tmp/certs")
urls = {
    "root.pem": "https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt",
    "sub.pem": "https://gu-st.ru/content/lending/russian_trusted_sub_ca_pem.crt",
}
for name, url in urls.items():
    if not (certs / name).exists():
        try:
            (certs / name).write_bytes(urllib.request.urlopen(url, timeout=20).read())
        except Exception as exc:  # noqa: BLE001
            print(f"WARNING: не скачан {url}: {exc}")
parts = [pathlib.Path(certifi.where()).read_text()]
parts += [p.read_text() for p in sorted(certs.glob("*.pem")) if "BEGIN CERTIFICATE" in p.read_text()]
pathlib.Path("/app/ca-bundle.pem").write_text("\n".join(parts))
print(f"ca-bundle: certifi + {len(parts) - 1} сертификат(а) НУЦ")
PY

COPY backend/app ./app
COPY backend/data ./data
COPY backend/scripts ./scripts
COPY backend/prompts ./prompts
COPY --from=front /front/dist ./static

ENV DATABASE_URL=sqlite:////data/app.db MAX_CA_BUNDLE=/app/ca-bundle.pem STATIC_DIR=/app/static
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

# Ровно один воркер: при двух напоминания уйдут дважды.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips=*"]
