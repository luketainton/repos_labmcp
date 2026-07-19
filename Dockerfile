FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.8.14 /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN uv sync --no-dev

ENV PATH="/app/.venv/bin:$PATH"
USER 10001:10001
ENTRYPOINT ["labmcp"]
