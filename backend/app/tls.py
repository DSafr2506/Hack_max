"""Доверенные сертификаты для исходящих HTTPS-запросов (API MAX, сайты организаторов)."""

from pathlib import Path

import certifi

from app.config import BACKEND_DIR, settings


def ca_bundle() -> str | bool:
    """Сертификаты для API MAX: certifi + корневой и выпускающий НУЦ Минцифры из backend/certs.

    В Docker бандл собран в образе (MAX_CA_BUNDLE=/app/ca-bundle.pem). При запуске без Docker
    указанного файла нет — собираем такой же рядом с кодом, руками ничего делать не нужно."""
    if settings.max_ca_bundle and Path(settings.max_ca_bundle).is_file():
        return settings.max_ca_bundle
    certs = sorted((BACKEND_DIR / "certs").glob("*.pem"))
    if not certs:
        return True
    out = BACKEND_DIR / "ca-bundle.pem"
    parts = [Path(certifi.where()).read_text(encoding="utf-8")]
    parts += [c.read_text(encoding="utf-8") for c in certs if "BEGIN CERTIFICATE" in c.read_text(encoding="utf-8")]
    out.write_text("\n".join(parts), encoding="utf-8")
    return str(out)
