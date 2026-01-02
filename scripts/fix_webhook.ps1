# Скрипт для быстрого исправления проблемы с webhook

Write-Host "🔧 Исправление проблемы с webhook" -ForegroundColor Cyan
Write-Host ""

# Шаг 1: Проверка доступности порта 80
Write-Host "1️⃣ Проверка порта 80..." -ForegroundColor Yellow
$port80 = Get-NetFirewallRule | Where-Object { $_.LocalPort -eq 80 -and $_.Direction -eq "Inbound" -and $_.Action -eq "Allow" -and $_.Enabled -eq $true }
if ($port80) {
    Write-Host "   ✅ Порт 80 открыт в firewall" -ForegroundColor Green
} else {
    Write-Host "   ⚠️  Порт 80 не открыт в firewall" -ForegroundColor Yellow
    Write-Host "   🔧 Открываю порт 80..." -ForegroundColor Yellow
    New-NetFirewallRule -DisplayName "HTTP Port 80 - Webhook" -Direction Inbound -LocalPort 80 -Protocol TCP -Action Allow -Enabled True
    Write-Host "   ✅ Порт 80 открыт" -ForegroundColor Green
}

# Шаг 2: Проверка доступности сервера
Write-Host ""
Write-Host "2️⃣ Проверка доступности сервера 192.168.1.64:80..." -ForegroundColor Yellow
try {
    $test = Test-NetConnection -ComputerName 192.168.1.64 -Port 80 -WarningAction SilentlyContinue
    if ($test.TcpTestSucceeded) {
        Write-Host "   ✅ Сервер доступен" -ForegroundColor Green
    } else {
        Write-Host "   ❌ Сервер недоступен" -ForegroundColor Red
        Write-Host "   💡 Проверьте, что Docker контейнеры запущены: docker-compose ps" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   ⚠️  Не удалось проверить доступность" -ForegroundColor Yellow
}

# Шаг 3: Проверка webhook endpoint
Write-Host ""
Write-Host "3️⃣ Проверка webhook endpoint..." -ForegroundColor Yellow
try {
    $body = '{"test":"data"}'
    $response = Invoke-WebRequest -Uri "http://localhost/events/webhook" -Method POST -ContentType "application/json" -Body $body -UseBasicParsing -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200) {
        Write-Host "   ✅ Webhook endpoint работает" -ForegroundColor Green
    }
} catch {
    Write-Host "   ⚠️  Webhook endpoint недоступен локально" -ForegroundColor Yellow
}

# Шаг 4: Инструкции
Write-Host ""
Write-Host "4️⃣ Следующие шаги:" -ForegroundColor Yellow
Write-Host "   📋 Проверьте настройки на терминале:" -ForegroundColor Cyan
Write-Host "      - Configuration → Network → HTTP Listening" -ForegroundColor White
Write-Host "      - Убедитесь, что HTTP Listening ВКЛЮЧЕН" -ForegroundColor White
Write-Host "      - Event Alarm IP: 192.168.1.64" -ForegroundColor White
Write-Host "      - URL: /events/webhook" -ForegroundColor White
Write-Host "      - Port: 80" -ForegroundColor White
Write-Host ""
Write-Host "   📋 Мониторинг логов:" -ForegroundColor Cyan
Write-Host "      docker-compose logs -f backend | Select-String -Pattern 'WEBHOOK'" -ForegroundColor White
Write-Host ""
Write-Host "   📋 Затем выполните авторизацию на терминале" -ForegroundColor Cyan
Write-Host ""

