# Анализ запросов веб-интерфейса Hikvision

Документация основана на анализе сетевого трафика веб-интерфейса терминала Hikvision.

## Последовательность запросов при создании пользователя

Веб-интерфейс терминала использует следующую последовательность:

1. **POST /ISAPI/AccessControl/CaptureFaceData** - Захват фото с терминала
2. **GET /ISAPI/Security/token?format=json** - Получение токена для доступа к фото
3. **GET /LOCALS/pic/web_face_enrollpic.jpg@WEB000000000172?token=...** - Скачивание фото
4. **GET /ISAPI/AccessControl/Door/param/1/capabilities** - Проверка возможностей двери
5. **POST /ISAPI/AccessControl/UserInfo/Record?format=json&security=1&iv=...** - Создание пользователя с фото (multipart)
6. **GET /ISAPI/Security/token?format=json** - Получение токена для FDSetUp
7. **PUT /ISAPI/Intelligent/FDLib/FDSetUp?format=json&token=...** - Настройка Face Detection Library

## Текущая реализация в системе

Наша система использует упрощенный двухэтапный процесс:

### Шаг 1: Создание пользователя (JSON API)

**Endpoint:** `POST /ISAPI/AccessControl/UserInfo/Record?format=json`

**Payload:** JSON (не multipart)

### Шаг 2: Добавление фото (FDLib JSON API)

**Endpoint:** `POST /ISAPI/Intelligent/FDLib?format=json`

**Payload:** JSON с base64-encoded фото

## Отличия от веб-интерфейса

1. **Не используем multipart** - вместо этого используем JSON API
2. **Не используем security=1 и iv** - эти параметры не требуются для JSON API
3. **Не вызываем FDSetUp** - настройка FDLib происходит автоматически

## Преимущества текущего подхода

- ✅ Проще в реализации
- ✅ Меньше запросов
- ✅ Более надежно (меньше точек отказа)
- ✅ Работает на всех версиях прошивки

## Примечания

Веб-интерфейс использует multipart для совместимости со старыми версиями прошивки. JSON API - более современный подход, который также поддерживается терминалом.

