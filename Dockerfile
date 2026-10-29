# Schulwissen-Plattform – Abbild für den Betrieb mit Docker Compose.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_PROJECT_ENVIRONMENT=/usr/local \
    UV_COMPILE_BYTECODE=1

# uv löst die Abhängigkeiten reproduzierbar aus uv.lock auf.
RUN pip install --no-cache-dir uv

WORKDIR /app

# Erst die Abhängigkeiten, damit Docker den Schritt bei Codeänderungen
# aus dem Zwischenspeicher nimmt.
COPY pyproject.toml uv.lock ./

# MIT_DEV=true nimmt pytest und ruff mit – für das Werkzeug-Abbild aus
# docker-compose.test.yml. Das Betriebsabbild bleibt ohne Testwerkzeuge.
ARG MIT_DEV=false
RUN if [ "$MIT_DEV" = "true" ]; then \
        uv sync --frozen --no-install-project; \
    else \
        uv sync --frozen --no-dev --no-install-project; \
    fi

COPY . .

# Statische Dateien einmal beim Bauen sammeln. Dafür genügen Platzhalterwerte –
# collectstatic braucht keine Datenbank.
RUN SW_DEBUG=true SW_SECRET_KEY=bauen SW_DATABASE_URL=postgresql://x:x@127.0.0.1:5432/x \
    python manage.py collectstatic --noinput --clear

RUN useradd --create-home --uid 10001 schulwissen \
    && mkdir -p /medien && chown schulwissen /medien
USER schulwissen

EXPOSE 8000
CMD ["/app/docker/start.sh"]
