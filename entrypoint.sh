#!/bin/bash
set -e

echo "⏳ Waiting for PostgreSQL at ${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432}..."
while ! nc -z "${POSTGRES_HOST:-db}" "${POSTGRES_PORT:-5432}"; do
  sleep 0.5
done
echo "✅ PostgreSQL is ready!"

# Only the web service runs migrations; celery workers skip this.
if [ "$RUN_MIGRATIONS" = "true" ]; then
  echo "🔄 Generating migration files..."
  python manage.py makemigrations users products auctions billing moderation --noinput

  echo "🔄 Applying database migrations..."
  python manage.py migrate --noinput

  echo "📦 Collecting static files..."
  python manage.py collectstatic --noinput 2>/dev/null || true
fi

exec "$@"
