# --- Stage 1: build the React frontend ---
FROM node:20-slim AS frontend
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: serve via FastAPI ---
FROM python:3.12-slim AS backend

# Build metadata: pasados como --build-arg para que el endpoint /api/version
# pueda mostrar qué versión del código está corriendo y cuándo se desplegó.
# Si el deploy se hace via deploy.sh, estos vienen del git HEAD del droplet.
ARG GIT_COMMIT=unknown
ARG GIT_COMMIT_DATE=unknown
ARG BUILD_TIME=unknown

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    GIT_COMMIT=$GIT_COMMIT \
    GIT_COMMIT_DATE=$GIT_COMMIT_DATE \
    BUILD_TIME=$BUILD_TIME

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY backend/app /app/backend/app
RUN pip install /app/backend

# Bake the built frontend into backend/static so FastAPI serves it.
COPY --from=frontend /app/dist /app/backend/static

WORKDIR /app/backend

# SQLite lives in /app/data (mount as a volume in compose).
ENV DATABASE_URL=sqlite:////app/data/banxico.db
RUN mkdir -p /app/data

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD curl -fsS http://localhost:8000/health || exit 1

# Respeta $PORT si el proveedor (Render/Railway/Fly) lo inyecta; local usa 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
