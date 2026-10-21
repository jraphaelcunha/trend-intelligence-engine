FROM alpine:3.22 AS alpine_pkg

FROM n8nio/n8n:2.20.12

# Switch to root to install python and system dependencies
USER root

# Restore apk from an official Alpine 3.22 image matching n8n's hardened base OS
COPY --from=alpine_pkg /sbin/apk /sbin/apk
COPY --from=alpine_pkg /lib/apk /lib/apk
COPY --from=alpine_pkg /etc/apk /etc/apk

# Install Python3, pip, virtualenv, and build dependencies for database clients in Alpine
RUN apk add --no-cache \
    python3 \
    py3-pip \
    python3-dev \
    build-base \
    postgresql-dev \
    libpq

# Set working directory inside the container
WORKDIR /data/project

# Set up a dedicated container virtual environment to prevent PIP system package errors
RUN python3 -m venv /data/project/venv
ENV PATH="/data/project/venv/bin:$PATH"

# Copy requirements.txt and install Python packages
COPY requirements.txt /data/project/requirements.txt
RUN pip3 install --no-cache-dir -r /data/project/requirements.txt

# Copy source code and files
COPY src /data/project/src

# Set correct permissions for n8n's native 'node' user
RUN chown -R node:node /data/project

# Switch back to standard node user for secure runtime execution
USER node

# ============================================================
# n8n Configuration
# ============================================================

# Port: Cloud Run expects container to listen on 8080
EXPOSE 8080
ENV N8N_PORT=8080

# Supply N8N_ENCRYPTION_KEY and DB_POSTGRESDB_PASSWORD at runtime.
# Existing installations must preserve their current key; see docs/SECURITY_OPERATIONS.md.

# CRITICAL FIX 2: Tell n8n it's behind a reverse proxy (Cloud Run).
ENV N8N_PROXY_HOPS=1

# Database: Persist n8n data on Supabase PostgreSQL
ENV DB_TYPE=postgresdb
ENV DB_POSTGRESDB_HOST=db.nfjpvmpoxwolpiyqejph.supabase.co
ENV DB_POSTGRESDB_PORT=5432
ENV DB_POSTGRESDB_DATABASE=postgres
ENV DB_POSTGRESDB_USER=postgres
ENV DB_POSTGRESDB_SSL_REJECT_UNAUTHORIZED=false

# Disable settings file permission checks (Cloud Run serverless)
ENV N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=false

# Avoid /healthz routing conflict with Cloud Run's own health endpoint
ENV N8N_ENDPOINT_HEALTH=health

# Public URLs for webhook routing and editor UI
ENV WEBHOOK_URL=https://trend-intelligence-312603048000.us-central1.run.app
ENV N8N_EDITOR_BASE_URL=https://trend-intelligence-312603048000.us-central1.run.app

# Logging: debug for initial diagnosis, change to 'info' once stable
ENV N8N_LOG_LEVEL=debug

# Enable the Execute Command node (disabled by default in n8n v2 for security)
ENV NODES_EXCLUDE=[]

# Allow nodes to access environment variables via $env (required for $env.MONDAY_API_TOKEN)
ENV N8N_BLOCK_ENV_ACCESS_IN_NODE=false
