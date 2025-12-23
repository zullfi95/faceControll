FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей для компиляции некоторых пакетов
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Копирование requirements и установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY . .

# Создание директории для загружаемых файлов
RUN mkdir -p /app/uploads

# Запуск приложения с hot reload для разработки
# Используем переменную окружения для переключения между dev и prod режимами
CMD ["sh", "-c", "if [ \"$ENVIRONMENT\" = \"development\" ]; then uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips '*' --reload; else uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips '*'; fi"]
