# Настройка Терминала Hikvision

## Поддерживаемые модели

- **DS-K1T343EFWX** - основная рекомендуемая модель
- **DS-K1T342** - Value Series
- **DS-K1T680** - Pro Series

Все модели должны поддерживать:
- ISAPI протокол
- HTTP Listening для событий
- Распознавание лиц
- Управление пользователями через API

## Первоначальная настройка

### 1. Доступ к веб-интерфейсу

1. Подключите терминал к сети
2. Найдите IP адрес терминала (через роутер или DHCP)
3. Откройте браузер: `http://<terminal-ip>`
4. Войдите с учетными данными по умолчанию:
   - **Логин:** `admin`
   - **Пароль:** `12345` (обязательно смените!)

### 2. Базовые настройки

#### Сеть
```
Configuration → Network → Basic Settings
- IP Address: Статический IP в офисной сети
- Subnet Mask: Согласно вашей сети
- Gateway: IP роутера
- DNS: Настройки DNS
```

#### Время
```
Configuration → System → Time Settings
- Time Zone: (GMT+04:00) Baku
- NTP Server: pool.ntp.org
- Sync with NTP: Включено
```

#### Безопасность
```
Configuration → Security → User Management
- Смените пароль администратора
- Создайте дополнительных пользователей при необходимости
- Настройте права доступа
```

### 3. ISAPI Настройки

#### Включение ISAPI
```
Configuration → Network → Advanced Settings → Integration Protocol
- ISAPI: Enabled
- Port: 80 (или 443 для HTTPS)
- Authentication: Digest/Basic
```

#### HTTP Listening (вебхуки)
```
Configuration → Network → Advanced Settings → HTTP Listening
- HTTP Listening: Enabled
- Event Alarm IP: 10.0.0.1 (VPN IP сервера)
- URL: /events/webhook
- Port: 8000
- Protocol: HTTP
- Method: POST
- Authentication: Enabled (если требуется)
```

### 4. Настройки распознавания лиц

#### Общие настройки
```
Configuration → Face Recognition → General Settings
- Face Recognition: Enabled
- Recognition Distance: 1-3 метра
- Recognition Angle: ±30°
- Liveness Detection: Enabled (если поддерживается)
```

#### Параметры захвата
```
Configuration → Face Recognition → Capture Settings
- Capture Mode: Auto
- Face Quality Threshold: 70%
- Face Size: 80x80 пикселей минимум
- Pose Angle Tolerance: Enabled
```

## Управление пользователями

### Через веб-интерфейс терминала

1. **Добавление пользователя**
   ```
   User Management → User
   - User Type: Normal User
   - Name: ФИО сотрудника
   - User ID: Уникальный ID (например, "001")
   - Card No: Номер карты (опционально)
   ```

2. **Загрузка фото**
   ```
   - Перейдите к пользователю
   - Face Recognition → Face Data
   - Upload Photo: Выберите фото лица
   - Quality Check: Убедитесь что качество >70%
   ```

### Через API (рекомендуемый способ)

Используйте веб-интерфейс системы для автоматического управления:

1. Добавьте терминал в системе: `Настройки → Устройства`
2. Создайте сотрудника: `Сотрудники → Добавить сотрудника`
3. Загрузите фото и нажмите `Синхронизировать с терминалом`

## API Endpoints

### Основные операции

#### Проверка подключения
```http
GET /ISAPI/System/deviceInfo
Authorization: Digest
```

#### Создание пользователя
```http
POST /ISAPI/AccessControl/UserInfo/User
Content-Type: application/xml

<?xml version="1.0" encoding="UTF-8"?>
<UserInfo>
    <employeeNo>001</employeeNo>
    <name>Test User</name>
    <userType>normal</userType>
    <Valid>
        <enable>true</enable>
        <beginTime>2024-01-01T00:00:00</beginTime>
        <endTime>2030-12-31T23:59:59</endTime>
    </Valid>
</UserInfo>
```

#### Загрузка фото
```http
POST /ISAPI/Intelligent/FDLib/FDSetUp?format=json
Content-Type: application/json

{
    "faceLibType": "blackFD",
    "FDID": "001",
    "FPID": "001",
    "faceData": "base64_encoded_image"
}
```

#### Получение списка пользователей
```http
GET /ISAPI/AccessControl/UserInfo/User?format=json
```

## Вебхуки (Events)

### Формат событий

Терминал отправляет события в формате JSON:

```json
{
    "AccessControllerEvent": {
        "employeeNoString": "001",
        "name": "Test User",
        "eventType": "entry",
        "cardReaderNo": "1",
        "eventTime": "2024-01-01T09:00:00+04:00",
        "deviceID": "DS-K1T343EFWX",
        "cardNo": "123456789"
    }
}
```

### Типы событий
- `entry` - вход сотрудника
- `exit` - выход сотрудника
- `heartBeat` - heartbeat (игнорируется)

### Обработка ошибок

Если терминал не отправляет события:
1. Проверьте VPN соединение: `ping 10.0.0.1`
2. Проверьте HTTP Listening настройки
3. Проверьте логи терминала
4. Убедитесь что API ключ правильный

## Диагностика

### Проверка подключения

```bash
# С сервера
curl -u admin:password http://10.0.0.100/ISAPI/System/deviceInfo

# Из веб-интерфейса системы
Настройки → Устройства → Проверить соединение
```

### Логи терминала

```
Maintenance → Log
- Фильтр по: Access Control
- Уровень: All
```

### Распространенные проблемы

#### "Connection timeout"
- Проверьте IP адрес терминала
- Убедитесь что терминал в сети
- Проверьте firewall настройки

#### "Authentication failed"
- Проверьте логин/пароль
- Убедитесь что ISAPI включен
- Попробуйте Digest аутентификацию

#### "Face not recognized"
- Улучшите освещение
- Проверьте качество фото
- Настройте параметры распознавания

#### "Events not sending"
- Проверьте HTTP Listening настройки
- Убедитесь что URL правильный: `/events/webhook`
- Проверьте API ключ в заголовках

## Производительность

### Рекомендации
- Максимум 500 пользователей на терминал
- Храните фото в высоком разрешении (200x200+ пикселей)
- Регулярно очищайте логи событий
- Мониторьте использование CPU/памяти

### Оптимизация
```
Configuration → System → Maintenance
- Log Retention: 30 дней
- Auto Backup: Disabled (если не нужно)
- Performance Mode: High Performance
```
