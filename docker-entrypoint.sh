#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
  sleep 0.5
done
echo "PostgreSQL is available"

python manage.py migrate --noinput
python manage.py collectstatic --noinput

if [ -n "$DJANGO_ADMIN_USERNAME" ] && [ -n "$DJANGO_ADMIN_EMAIL" ] && [ -n "$DJANGO_ADMIN_PASSWORD" ]; then
    python manage.py shell -c "
import os
from django.contrib.auth import get_user_model
User = get_user_model()
username = os.environ.get('DJANGO_ADMIN_USERNAME')
email = os.environ.get('DJANGO_ADMIN_EMAIL')
password = os.environ.get('DJANGO_ADMIN_PASSWORD')
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, email, password)
    print(f'Created superuser: {username}')
else:
    print(f'Superuser already exists: {username}')
"
fi

exec "$@"
