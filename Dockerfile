FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN uv sync --no-dev

ENV PATH="/app/.venv/bin:$PATH"
ENV HOME=/home/labmcp \
    XDG_DATA_HOME=/home/labmcp/.local/share

RUN mkdir -p "$XDG_DATA_HOME" && chown -R 10001:10001 /home/labmcp

USER 10001:10001
ENTRYPOINT ["labmcp"]
