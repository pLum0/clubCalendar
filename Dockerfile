FROM python:3.11-alpine

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Alpine base (small attack surface). The entrypoint + compose command are POSIX
# sh, so no bash is needed. psycopg2 has no musl wheel, so it's compiled with
# temporary build deps; libpq is its runtime library.
RUN apk add --no-cache postgresql-client netcat-openbsd gettext curl nodejs npm libpq

COPY requirements.txt requirements-dev.txt ./
RUN apk add --no-cache --virtual .build-deps gcc musl-dev postgresql-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-dev.txt \
    && apk del .build-deps

COPY package.json package-lock.json* ./
RUN npm install --ignore-scripts

COPY . .

RUN mkdir -p /app/staticfiles && chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
# One worker, many threads: requests wait on a slow external HTTP call, not on
# CPU, so threads are what buys concurrency here. Staying at a single worker
# keeps the sheet cache's in-process locks meaningful, so concurrent readers of
# one week share a fetch instead of each starting their own.
#
# The timeout has to outlast the slowest request, not the slowest outbound call:
# a booking makes two calls back to back and a removal three, each with its own
# budget. Threads are what make a generous value cheap -- a request sitting on
# one no longer holds up the others, so this only has to be high enough to still
# catch a genuinely hung worker.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--worker-class", "gthread", "--workers", "1", "--threads", "8", "--timeout", "300", "calendar_project.wsgi:application"]
