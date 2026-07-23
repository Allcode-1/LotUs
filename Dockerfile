FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl openssl \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

RUN mkdir -p certs \
    && chmod +x scripts/docker-entrypoint.sh \
    && addgroup --system lotus \
    && adduser --system --ingroup lotus --home /app lotus \
    && chown -R lotus:lotus /app

USER lotus

EXPOSE 8000

ENTRYPOINT ["scripts/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
