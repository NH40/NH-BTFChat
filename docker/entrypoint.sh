#!/usr/bin/env sh
set -e

# С аргументами (сервис api) — выполнить их как есть; без — миграции и бот.
if [ "$#" -gt 0 ]; then
    exec "$@"
fi

python -m alembic upgrade head
exec python -m bot.main
