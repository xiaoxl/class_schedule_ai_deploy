FROM ghcr.io/astral-sh/uv:0.10.2 AS uv
FROM python:3.13-slim

COPY --from=uv /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock README.md .python-version ./
COPY config ./config
COPY src ./src

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PORT=8000

EXPOSE 8000

CMD ["sh", "-c", "uvicorn class_schedule.webapp:app --host 0.0.0.0 --port ${PORT}"]
