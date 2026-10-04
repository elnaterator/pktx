# Multi-stage build for pktx MCP server with React frontend
# Stage 1: Frontend builder - build React SPA
FROM node:22-slim@sha256:43ac6c60b8f89723f746e8a92ce91abd5017e627ce1ddfe4238355d3a30b772c AS frontend-builder

WORKDIR /frontend

# Copy frontend dependency files
COPY frontend/package.json frontend/package-lock.json* ./

# Install frontend dependencies
RUN npm ci

# Copy frontend source
COPY frontend/ ./

# Build-time env var — Vite inlines VITE_* vars into the JS bundle at build time.
# Pass via: docker build --build-arg VITE_CLERK_PUBLISHABLE_KEY=pk_...
ARG VITE_CLERK_PUBLISHABLE_KEY
ENV VITE_CLERK_PUBLISHABLE_KEY=$VITE_CLERK_PUBLISHABLE_KEY

# Build production bundle
RUN npm run build

# Stage 2: Backend builder - install Python dependencies
FROM python:3.11-slim@sha256:bab1b7ef4b450c81002278d035eff85ebe394ae94df904f7a3ba14f7e16e487b AS backend-builder

# Install uv for dependency management
COPY --from=ghcr.io/astral-sh/uv:0.12.23@sha256:61d393e44e249f2e4b526b6c7ddcecce245946826e608e11c93ad4f5bba55b21 /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy backend dependency files
COPY backend/pyproject.toml backend/uv.lock ./

# Copy backend source (needed for package installation)
COPY backend/src ./src

# Install dependencies and the pktx package
RUN uv sync --frozen --no-dev

# Stage 3: Runtime - minimal image with both frontend and backend
FROM python:3.11-slim@sha256:bab1b7ef4b450c81002278d035eff85ebe394ae94df904f7a3ba14f7e16e487b

# Pull Debian security fixes newer than the pinned base digest, and drop the
# system pip/setuptools (the app runs from /app/.venv; they only add CVE surface)
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /usr/local/lib/python3.11/site-packages/setuptools* \
              /usr/local/lib/python3.11/site-packages/_distutils_hack \
              /usr/local/lib/python3.11/site-packages/distutils-precedence.pth \
    && python -m pip uninstall -y pip

# Set working directory
WORKDIR /app

# Copy installed Python dependencies from backend-builder
COPY --from=backend-builder /app/.venv /app/.venv

# Copy backend application source
COPY backend/src/ /app/src/

# Copy frontend build output
COPY --from=frontend-builder /frontend/dist /app/frontend-dist

# Set Python path and environment
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1 \
    PKTX_DATA_DIR=/data \
    PKTX_FRONTEND_DIR=/app/frontend-dist

# Create data directory and an unprivileged runtime user (Lambda overrides the
# user anyway; this keeps docker compose / self-hosted runs off root)
RUN useradd --system --uid 10001 --no-create-home pktx \
    && mkdir -p /data \
    && chown pktx /data

# Lambda Web Adapter — bridges Lambda events to the app's localhost HTTP server
# No-op when running outside Lambda (AWS_LWA_PORT is ignored by the app directly)
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4@sha256:e2653f741cd15851ba4f13f3cc47d29f2d14377c7d11737bfa272baa1b569007 /lambda-adapter /opt/extensions/lambda-adapter
ENV AWS_LWA_PORT=8000

# Expose default port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; import os; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PKTX_PORT\", \"8000\")}/health')"

USER pktx

# Run the server
CMD ["python", "-m", "pktx.server"]
