# Бэкенд: FastAPI + планировщик напоминаний + приём событий MAX в одном процессе.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Корневой и выпускающий сертификаты НУЦ Минцифры: API MAX подписан ими.
# httpx берёт доверенные сертификаты из certifi, поэтому собираем общий бандл.
# Если сайт с сертификатами недоступен при сборке — положите их в backend/certs/ заранее.
COPY certs/ /tmp/certs/
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

COPY app ./app
COPY data ./data
COPY scripts ./scripts

ENV DATABASE_URL=sqlite:////data/app.db MAX_CA_BUNDLE=/app/ca-bundle.pem
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

# Ровно один воркер: при двух напоминания уйдут дважды.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips=*"]
