# Beacon API — FastAPI on Cloud Run.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

# Cloud Run injects $PORT (default 8080). Shell form so it expands.
ENV PORT=8080
CMD exec uvicorn app.api:app --host 0.0.0.0 --port ${PORT}
