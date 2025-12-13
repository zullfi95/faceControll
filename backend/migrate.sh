#!/bin/bash
# Скрипт для выполнения миграции через docker-compose

echo "Выполнение миграции базы данных..."

# Проверяем, запущен ли docker-compose
if docker-compose ps | grep -q "db.*Up"; then
    echo "База данных запущена в Docker"
    
    # Выполняем миграцию через docker-compose exec
    docker-compose exec -T db psql -U postgres -d facerecog < migrations/001_add_event_fields.sql
    
    if [ $? -eq 0 ]; then
        echo "✅ Миграция выполнена успешно!"
    else
        echo "❌ Ошибка при выполнении миграции"
        exit 1
    fi
else
    echo "База данных не запущена в Docker"
    echo "Выполните миграцию вручную:"
    echo "  psql -U postgres -d facerecog -f migrations/001_add_event_fields.sql"
    exit 1
fi

