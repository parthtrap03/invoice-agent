# ---- Stage 1: build the React frontend ----
FROM node:20-slim AS frontend

WORKDIR /ui
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python backend, serving the built UI ----
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY uploads/demo/ uploads/demo/
COPY --from=frontend /ui/dist frontend/dist

ENV APP_ENV=production \
    DEBUG=false \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Render/Railway inject $PORT; default to 8000 locally
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
