FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.24 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

WORKDIR /workspace
ENTRYPOINT ["/app/.venv/bin/sts2-tas"]
CMD ["--help"]
