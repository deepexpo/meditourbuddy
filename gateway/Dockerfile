FROM python:3.12-slim

# Install Node.js 20 LTS so the gateway can spawn the clinic-registry-mcp
# subprocess (packages/clinic-registry-mcp/dist/index.js) via `node`.
# Without this, mcp_manager.connect() fails silently and every /cases call
# and /health?mcp_connected will be false.
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
