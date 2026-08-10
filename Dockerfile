FROM node:22-bookworm-slim AS frontend-builder

WORKDIR /app/frontend
RUN corepack enable && corepack prepare pnpm@11.16.0 --activate
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build


FROM python:3.12-slim-bookworm AS application

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PORT=10000

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libx11-6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN python -m pip install --no-cache-dir .

COPY --from=frontend-builder /app/frontend/dist ./frontend/dist
RUN mkdir -p generated/web

EXPOSE 10000

CMD ["sh", "-c", "python -m uvicorn prompt2cad.web_app:app --host 0.0.0.0 --port ${PORT}"]
