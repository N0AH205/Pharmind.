# Build stage for Next.js frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED 1
ENV BACKEND_URL=http://127.0.0.1:8000
RUN npm run build

# Final runner stage (Python + Node static server or FastAPI mounting)
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies (for RDKit / C++ libs if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libxrender1 \
    libxext6 \
    libsm6 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for serving frontend alongside backend if needed, or static serving
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r ./backend/requirements.txt

# Copy backend source
COPY backend/ ./backend/
COPY data/ ./data/

# Copy built frontend assets
COPY --from=frontend-builder /app/frontend/.next ./frontend/.next
COPY --from=frontend-builder /app/frontend/public ./frontend/public
COPY --from=frontend-builder /app/frontend/package*.json ./frontend/
COPY --from=frontend-builder /app/frontend/node_modules ./frontend/node_modules

# Expose ports
EXPOSE 3000 8000

# Copy start script
COPY docker-start.sh /app/docker-start.sh
RUN chmod +x /app/docker-start.sh

CMD ["/app/docker-start.sh"]
