# Udyam Digital API. On start it seeds SQLite if the database file is missing, so a fresh deploy (and every restart on a free plan
# with an ephemeral disk) begins from the same demo data: 25 products, both registries, 5,000 scored leads, 5 agents, demo users.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /srv/backend/
COPY data/ /srv/data/

# Uploaded KYC documents live here: outside anything served over HTTP, encrypted per file, purged after retention.
ENV DATA_DIR=/srv/data \
    DATABASE_URL=sqlite:////srv/db/udyam.db \
    UPLOAD_DIR=/srv/storage \
    PYTHONUNBUFFERED=1 \
    OMP_THREAD_LIMIT=1
RUN mkdir -p /srv/db /srv/storage && chmod +x start.sh

EXPOSE 8000
CMD ["./start.sh"]
