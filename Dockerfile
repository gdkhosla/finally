# Stage 1: Build Next.js static export
FROM node:20-slim AS frontend-build

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# Stage 2: Python backend + static files
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install backend dependencies
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

# Copy backend application code
COPY backend/ ./

# Copy the frontend static export into /app/static
COPY --from=frontend-build /frontend/out /app/static

# Ensure the DB directory exists for the volume mount
RUN mkdir -p /app/db

EXPOSE 8000

ENV FINALLY_DB_PATH=/app/db/finally.db

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
