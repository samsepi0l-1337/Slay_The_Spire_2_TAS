FROM python:3.14-slim

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir .

WORKDIR /workspace

ENTRYPOINT ["sts2-tas"]
CMD ["--help"]
