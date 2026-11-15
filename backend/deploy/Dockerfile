# Backend image for Cloud Run. The build context is backend/, not deploy/:
#   cd backend && docker build -f deploy/Dockerfile -t firecal-backend .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY requirements.txt ./
COPY deploy/requirements.txt deploy/
RUN pip install --no-cache-dir -r deploy/requirements.txt

# Only what the server needs (no .venv, tests or caches).
COPY main.py ./
COPY src/ src/
COPY test/mock_data/ test/mock_data/
COPY deploy/wsgi.py deploy/

# Cloud Run sets $PORT. One worker = one copy of the data in memory; threads
# answer requests in parallel. --timeout 0 leaves timeouts to Cloud Run.
CMD exec gunicorn --bind ":$PORT" --workers 1 --threads 8 --timeout 0 deploy.wsgi:app
