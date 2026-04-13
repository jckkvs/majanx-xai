# frontend build
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# backend run
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY core/ ./core/
COPY server/ ./server/
COPY game.py .
COPY --from=frontend-builder /app/frontend/dist ./static/

EXPOSE 8000
CMD ["uvicorn", "game:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
