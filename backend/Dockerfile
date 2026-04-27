FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libreoffice \
       fontconfig \
       fonts-liberation \
       fonts-dejavu-core \
       fonts-noto-core \
       fonts-crosextra-caladea \
       fonts-crosextra-carlito \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY .env.example ./.env.example
COPY docker-entrypoint.sh ./docker-entrypoint.sh

RUN mkdir -p /app/runtime/templates /app/runtime/temp /app/data \
    && chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
