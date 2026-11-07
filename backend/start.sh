#!/bin/sh
# Seed on first start, with the deployment's own secrets: phone hashes and encrypted columns depend on PII_HASH_KEY and
# APP_ENCRYPTION_KEY, so a database seeded with other keys would not recognise the demo staff logins.
set -e
DB_FILE="${DATABASE_URL#sqlite:///}"
if [ ! -s "$DB_FILE" ]; then
  echo "seeding $DB_FILE"
  python -m app.seed
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*'
