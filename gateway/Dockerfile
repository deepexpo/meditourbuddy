# ─── Stage 1: Build the clinic-registry-mcp server ─────────────────────────
# dist/ is gitignored so we must compile from source.
# `pnpm deploy` produces a self-contained directory (dist/ + production
# node_modules, workspace symlinks resolved) that Stage 2 can just COPY.
FROM node:22-slim AS mcp-builder

# Install pnpm (must match packageManager field in root package.json)
RUN npm install -g pnpm@11.9.0 --quiet

WORKDIR /repo

# Copy workspace manifests first so dependency installs are cached separately
# from source changes.
COPY pnpm-workspace.yaml pnpm-lock.yaml package.json tsconfig.base.json ./
COPY packages/shared/package.json          ./packages/shared/
COPY packages/clinic-registry-mcp/package.json ./packages/clinic-registry-mcp/

# Install all workspace deps (including dev — needed for tsc)
RUN pnpm install --frozen-lockfile

# Copy source files for both packages
COPY packages/shared/       ./packages/shared/
COPY packages/clinic-registry-mcp/ ./packages/clinic-registry-mcp/

# Build shared first (clinic-registry-mcp depends on it)
RUN pnpm --filter @meditourbuddy/shared build

# Build clinic-registry-mcp
RUN pnpm --filter @meditourbuddy/clinic-registry-mcp build

# Create a standalone deployment: resolves workspace symlinks, copies only
# production deps — output is a normal self-contained node project.
# --legacy: pnpm v10+ defaults to requiring inject-workspace-packages=true
# for `pnpm deploy`; --legacy keeps the old (self-contained, no external
# symlinks) behavior without changing how the rest of the install works.
RUN pnpm --filter @meditourbuddy/clinic-registry-mcp deploy --prod --legacy /deploy/mcp


# ─── Stage 2: Python gateway + Node runtime ─────────────────────────────────
FROM python:3.12-slim

# Install Node.js runtime (LTS) so the gateway can spawn the MCP subprocess.
# We only need the runtime — build tools stay in Stage 1.
RUN apt-get update && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the self-contained MCP server from the builder stage.
COPY --from=mcp-builder /deploy/mcp/ ./mcp_server/

# Install Python dependencies (gateway only)
COPY gateway/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the gateway application source
COPY gateway/ .

# Bake in the MCP server path as the default — can be overridden by Fly secret.
ENV MCP_SERVER_COMMAND="node"
ENV MCP_SERVER_ARGS="/app/mcp_server/dist/index.js"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
