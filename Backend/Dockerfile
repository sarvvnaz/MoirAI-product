FROM python:3.11-slim

# Unbuffered so uvicorn/print logs reach the platform's log viewer immediately.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /srv

# Dependencies first: this layer is cached until requirements.txt changes.
COPY app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Runtime writes (SQLite + generated reminder images) go here. Mount the
# persistent disk at /data — without it, every redeploy wipes participant data.
ENV DATA_DIR=/data
RUN mkdir -p /data

EXPOSE 8000

# Bind to $PORT when the platform injects one, else 8000. A host whose proxy
# assigns a port will 502 against a hardcoded one — the app is running, just
# not where the proxy is looking.
#
# `exec` so uvicorn replaces the shell and still receives SIGTERM directly,
# which keeps shutdown clean despite the shell-form CMD.
#
# --proxy-headers/--forwarded-allow-ips: the app sits behind the platform's
# TLS-terminating proxy, so without these it sees every request as plain http
# from the proxy's IP and builds redirects with the wrong scheme.
#
# One worker: SQLite tolerates only a single writer. Raise --workers only
# after moving DATABASE_URL to Postgres.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
