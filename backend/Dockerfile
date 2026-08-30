FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/

WORKDIR /app/backend
EXPOSE 8000

# Shell form (not exec-form JSON array) so $PORT actually gets expanded —
# hosts like Render assign their own port via this env var and expect the
# app to bind to it, not a hardcoded one. Falls back to 8000 for
# docker-compose/local use, where PORT is never set.
CMD uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}
