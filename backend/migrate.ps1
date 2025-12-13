# PowerShell скрипт для выполнения миграции через docker-compose

Write-Host "Выполнение миграции базы данных..." -ForegroundColor Cyan

# Проверяем, запущен ли docker-compose
$dbRunning = docker-compose ps | Select-String "db.*Up"

if ($dbRunning) {
    Write-Host "База данных запущена в Docker" -ForegroundColor Green
    
    # Выполняем миграцию через docker-compose exec
    Get-Content migrations/001_add_event_fields.sql | docker-compose exec -T db psql -U postgres -d facerecog
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Миграция выполнена успешно!" -ForegroundColor Green
    } else {
        Write-Host "❌ Ошибка при выполнении миграции" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "База данных не запущена в Docker" -ForegroundColor Yellow
    Write-Host "Выполните миграцию вручную:" -ForegroundColor Yellow
    Write-Host "  psql -U postgres -d facerecog -f migrations/001_add_event_fields.sql" -ForegroundColor Yellow
    exit 1
}

