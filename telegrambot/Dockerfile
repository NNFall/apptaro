FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libreoffice \
       fonts-liberation fonts-dejavu-core fonts-noto-core \
       fonts-crosextra-caladea fonts-crosextra-carlito \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
