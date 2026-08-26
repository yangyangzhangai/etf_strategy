FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ETF_CACHE_DB=/data/cache.sqlite3

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

VOLUME ["/data"]
EXPOSE 8000
CMD ["sh", "-c", "uvicorn etf_timing.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
