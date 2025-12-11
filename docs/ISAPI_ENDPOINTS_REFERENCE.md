# Hikvision ISAPI Endpoints - Полный справочник

Документ содержит полный список всех ISAPI endpoints, используемых в проекте FaceControll, с подробными описаниями, методами HTTP и примерами использования.

**Версия:** 1.0  
**Дата обновления:** 2025-01-09  
**Источники:** 
- Официальная документация Hikvision ISAPI
- HAR файлы с реальными запросами
- Код проекта (hikvision_client.py, main.py)

---

## Содержание

1. [Security (Безопасность)](#security-безопасность)
2. [System (Система)](#system-система)
3. [AccessControl (Контроль доступа)](#accesscontrol-контроль-доступа)
4. [Intelligent/FDLib (Библиотека лиц)](#intelligentfdlib-библиотека-лиц)
5. [Streaming (Потоковое видео)](#streaming-потоковое-видео)
6. [Event (События)](#event-события)
7. [Другие модули](#другие-модули)

---

## Security (Безопасность)

### 1. Получение токена безопасности

**Endpoint:** `GET /ISAPI/Security/token?format=json`

**Описание:** Получение токена безопасности для использования в запросах. Токен кэшируется и обновляется при необходимости. Токены обычно действительны 30 минут.

**Метод:** GET

**Параметры:**
- `format=json` - формат ответа (JSON)

**Ответ:**
```json
{
  "Token": {
    "value": "pUCbUZqSIjUIrCJ7aqi3ddN8AU2aeDzi"
  }
}
```

**Использование:** Токен требуется для некоторых операций, например, `FDSetUp`.

---

### 2. Возможности админ-доступа

**Endpoint:** `GET /ISAPI/Security/adminAccesses/capabilities`

**Описание:** Получение информации о возможностях админ-доступа и управления пользователями системы.

**Метод:** GET

**Ответ:** XML или JSON с информацией о поддерживаемых функциях администрирования.

---

### 3. Поддержание сессии (Heartbeat)

**Endpoint:** `POST /ISAPI/Security/sessionHeartbeat`

**Описание:** Поддержание активной сессии с устройством. Используется для предотвращения таймаута сессии.

**Метод:** POST

**Ответ:**
```xml
<RequestStatus version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">
  <RequestURL>/ISAPI/Security/sessionHeartbeat</RequestURL>
  <statusCode>1</statusCode>
  <statusString>OK</statusString>
  <subStatusCode>ok</subStatusCode>
</RequestStatus>
```

**Использование:** Вызывается периодически для поддержания сессии активной.

---

## System (Система)

### 4. Информация об устройстве

**Endpoint:** `GET /ISAPI/System/deviceInfo`

**Описание:** Получение информации об устройстве: модель, серийный номер, версия прошивки, deviceID.

**Метод:** GET

**Ответ (XML):**
```xml
<DeviceInfo>
  <deviceName>DS-K1T343EFWX</deviceName>
  <serialNumber>...</serialNumber>
  <firmwareVersion>...</firmwareVersion>
  <deviceID>...</deviceID>
</DeviceInfo>
```

**Использование:** Первый запрос для проверки подключения и получения информации об устройстве.

---

### 5. Возможности системы

**Endpoint:** `GET /ISAPI/System/capabilities?format={format}`

**Описание:** Получение информации о поддерживаемых функциях системы: перезагрузка, сброс к заводским настройкам, обновление прошивки, снимки, предпросмотр и т.д.

**Метод:** GET

**Параметры:**
- `format=json` или `format=xml` - формат ответа

**Ответ:** Информация о поддерживаемых функциях системы.

---

### 6. Перезагрузка устройства

**Endpoint:** `PUT /ISAPI/System/reboot`

**Описание:** Отправка команды перезагрузки устройства.

**Метод:** PUT

**Ответ:** Статус выполнения операции.

**Внимание:** Устройство перезагрузится после выполнения команды.

---

### 7. Язык устройства

**Endpoint:** `GET /ISAPI/System/DeviceLanguage`

**Описание:** Получение текущего языка интерфейса устройства.

**Метод:** GET

**Ответ:** Информация о языке устройства.

---

### 8. Каналы видео

**Endpoint:** `GET /ISAPI/System/Video/inputs/channels`

**Описание:** Получение информации о доступных видео каналах устройства.

**Метод:** GET

**Ответ:** Список видео каналов.

---

## AccessControl (Контроль доступа)

### Capabilities (Возможности)

#### 9. Основные возможности AccessControl

**Endpoint:** `GET /ISAPI/AccessControl/capabilities?format=json`

**Описание:** Получение информации о поддерживаемых функциях контроля доступа. Проверка поддержки управления пользователями (`isSupportUserInfo`), удаленной проверки (`isSupportRemoteCheck`), удаления пользователей (`isSupportUserInfoDetailDelete`) и других функций.

**Метод:** GET

**Параметры:**
- `format=json` - формат ответа

**Ответ:**
```json
{
  "AccessControl": {
    "isSupportUserInfo": true,
    "isSupportRemoteCheck": true,
    "isSupportUserInfoDetailDelete": true,
    "isSupportAntiPassbackResetRules": true,
    "isSupportUserRightPlanTemplate": true,
    "EmployeeNoInfo": {
      "employeeNo": 32,
      "characterType": "any",
      "isSupportCompress": false
    }
  }
}
```

**Использование:** Первый запрос для проверки поддерживаемых функций перед выполнением операций.

---

#### 10. Возможности UserInfo

**Endpoint:** `GET /ISAPI/AccessControl/UserInfo/capabilities?format=json`

**Описание:** Получение информации о поддерживаемых операциях с пользователями: поиск (`get`), добавление (`post`), редактирование (`put`), применение (`setUp`).

**Метод:** GET

**Ответ:**
```json
{
  "UserInfo": {
    "supportFunction": ["get", "post", "put", "setUp"],
    "maxRecordNum": 10000
  }
}
```

---

#### 11. Возможности конфигурации ACS

**Endpoint:** `GET /ISAPI/AccessControl/AcsCfg/capabilities?format=json`

**Описание:** Получение информации о возможностях конфигурации системы контроля доступа (ACS).

**Метод:** GET

---

#### 12. Возможности захвата лица

**Endpoint:** `GET /ISAPI/AccessControl/CaptureFaceData/capabilities`

**Описание:** Получение информации о возможностях захвата фото лица с устройства.

**Метод:** GET

---

#### 13. Возможности захвата отпечатка

**Endpoint:** `GET /ISAPI/AccessControl/CaptureFingerPrint/capabilities`

**Описание:** Получение информации о возможностях захвата отпечатка пальца.

**Метод:** GET

---

#### 14. Возможности захвата карты

**Endpoint:** `GET /ISAPI/AccessControl/CaptureCardInfo/capabilities`

**Описание:** Получение информации о возможностях захвата информации с карты доступа.

**Метод:** GET

---

#### 15. Возможности карт

**Endpoint:** `GET /ISAPI/AccessControl/CardInfo/capabilities`

**Описание:** Получение информации о возможностях работы с картами доступа.

**Метод:** GET

---

#### 16. Возможности конфигурации отпечатков

**Endpoint:** `GET /ISAPI/AccessControl/FingerPrintCfg/capabilities?format=json`

**Описание:** Получение информации о возможностях конфигурации отпечатков пальцев.

**Метод:** GET

---

#### 17. Возможности конфигурации RFID карт

**Endpoint:** `GET /ISAPI/AccessControl/Configuration/RFCardCfg/capabilities?format=json`

**Описание:** Получение информации о возможностях конфигурации RFID карт.

**Метод:** GET

---

#### 18. Возможности двери

**Endpoint:** `GET /ISAPI/AccessControl/Door/param/{doorNo}/capabilities`

**Описание:** Получение информации о возможностях конкретной двери.

**Метод:** GET

**Параметры:**
- `doorNo` - номер двери (например, 1)

---

#### 19. Возможности удаления пользователя

**Endpoint:** `GET /ISAPI/AccessControl/UserInfoDetail/Delete/capabilities?format=json`

**Описание:** Проверка поддержки удаления пользователей устройством.

**Метод:** GET

---

#### 20. Возможности групп

**Endpoint:** `GET /ISAPI/AccessControl/LocalAttendance/group/capabilities?format=json`

**Описание:** Получение информации о возможностях работы с группами/департаментами.

**Метод:** GET

---

#### 21. Возможности поиска групп

**Endpoint:** `GET /ISAPI/AccessControl/LocalAttendance/groupSearch/capabilities?format=json`

**Описание:** Получение информации о возможностях поиска групп.

**Метод:** GET

---

#### 22. Возможности черного списка ID

**Endpoint:** `GET /ISAPI/AccessControl/IDBlackListCfg/capabilities`

**Описание:** Получение информации о возможностях работы с черным списком ID карт.

**Метод:** GET

---

#### 23. Возможности белого списка ID

**Endpoint:** `GET /ISAPI/AccessControl/IDAllowList/Task/capabilities?format=json`

**Описание:** Получение информации о возможностях работы с белым списком ID карт.

**Метод:** GET

---

#### 24. Возможности экспорта шаблона

**Endpoint:** `GET /ISAPI/AccessControl/DataImportAndExport/ExportUserDataTemplate/capabilities?format=json`

**Описание:** Получение информации о возможностях экспорта шаблона данных пользователей.

**Метод:** GET

---

### UserInfo (Информация о пользователях)

#### 25. Создание пользователя

**Endpoint:** `POST /ISAPI/AccessControl/UserInfo/Record?format=json`

**Описание:** Создание нового пользователя на устройстве. Если пользователь уже существует, устройство вернет ошибку.

**Метод:** POST

**Тело запроса:**
```json
{
  "UserInfo": {
    "employeeNo": "12345",
    "name": "Иван Иванов",
    "userType": "normal",
    "Valid": {
      "enable": false,
      "beginTime": "2025-01-01T00:00:00",
      "endTime": "2035-01-01T00:00:00",
      "timeType": "local"
    },
    "gender": "unknown",
    "doorRight": "1",
    "RightPlan": [{"doorNo": 1, "planTemplateNo": "1"}],
    "groupId": 1
  }
}
```

**Ответ:** Информация о созданном пользователе.

**Примечание:** Перед вызовом проверьте поддержку через `/ISAPI/AccessControl/UserInfo/capabilities` (должен содержать `"post"` в `supportFunction`).

---

#### 26. Создание пользователя (с шифрованием)

**Endpoint:** `POST /ISAPI/AccessControl/UserInfo/Record?format=json&security=1&iv={iv}`

**Описание:** Создание пользователя с шифрованием данных. Используется для безопасной передачи данных.

**Метод:** POST

**Параметры:**
- `security=1` - включение шифрования
- `iv={iv}` - initialization vector (32 hex символа, 128 бит)

**Тело запроса:** То же, что и в обычном создании пользователя.

**Использование:** Рекомендуется для передачи конфиденциальных данных.

---

#### 27. Применение настроек пользователя

**Endpoint:** `PUT /ISAPI/AccessControl/UserInfo/SetUp?format=json`

**Описание:** Применение информации о пользователе к устройству. Если пользователь существует, информация будет обновлена; если нет - пользователь будет создан.

**Метод:** PUT

**Тело запроса:**
```json
{
  "UserInfo": {
    "employeeNo": "12345"
  }
}
```

**Примечание:** Проверьте поддержку через capabilities (должен содержать `"setUp"` в `supportFunction`).

---

#### 28. Изменение пользователя

**Endpoint:** `PUT /ISAPI/AccessControl/UserInfo/Modify?format=json`

**Описание:** Редактирование информации существующего пользователя. Если пользователь не существует, устройство вернет ошибку.

**Метод:** PUT

**Тело запроса:**
```json
{
  "UserInfo": {
    "employeeNo": "12345",
    "name": "Обновленное Имя"
  }
}
```

**Примечание:** Проверьте поддержку через capabilities (должен содержать `"put"` в `supportFunction`).

---

#### 29. Количество пользователей

**Endpoint:** `GET /ISAPI/AccessControl/UserInfo/Count?format=json`

**Описание:** Получение количества пользователей, добавленных на устройство.

**Метод:** GET

**Ответ:**
```json
{
  "UserInfoCount": {
    "userNumber": 150
  }
}
```

**Использование:** Для проверки количества пользователей перед операциями.

---

#### 30. Поиск пользователей

**Endpoint:** `POST /ISAPI/AccessControl/UserInfo/Search?format=json`

**Описание:** Поиск информации о пользователях. Результаты возвращаются постранично.

**Метод:** POST

**Тело запроса:**
```json
{
  "UserInfoSearchCond": {
    "searchID": "1",
    "searchResultPosition": 0,
    "maxResults": 30
  }
}
```

**Ответ:**
```json
{
  "UserInfoSearch": {
    "searchID": "1",
    "responseStatus": "more",
    "numOfMatches": 150,
    "UserInfo": [
      {
        "employeeNo": "12345",
        "name": "Иван Иванов",
        "userType": "normal",
        "numOfFace": 1
      }
    ]
  }
}
```

**Примечание:** Проверьте поддержку через capabilities (должен содержать `"get"` в `supportFunction`).

---

#### 31. Поиск пользователей (с шифрованием)

**Endpoint:** `POST /ISAPI/AccessControl/UserInfo/Search?format=json&security=1&iv={iv}`

**Описание:** Поиск пользователей с шифрованием данных.

**Метод:** POST

**Параметры:**
- `security=1` - включение шифрования
- `iv={iv}` - initialization vector

---

#### 32. Детали пользователя

**Endpoint:** `GET /ISAPI/AccessControl/UserInfo/Detail?format=json&employeeNo={employee_no}`

**Описание:** Получение детальной информации о конкретном пользователе по его employeeNo.

**Метод:** GET

**Параметры:**
- `employeeNo` - ID сотрудника

**Ответ:**
```json
{
  "UserInfo": {
    "employeeNo": "12345",
    "name": "Иван Иванов",
    "numOfFace": 1,
    "faceURL": "/ISAPI/AccessControl/UserFace/faceData?..."
  }
}
```

**Использование:** Альтернативный метод получения информации о пользователе, не требующий прав на UserInfo/Search.

---

#### 33. Удаление пользователя (PUT метод)

**Endpoint:** `PUT /ISAPI/AccessControl/UserInfoDetail/Delete?format=json`

**Описание:** Удаление пользователя с устройства. Устройство начнет выполнение удаления, но это не означает, что пользователь уже удален. Используйте `/UserInfoDetail/DeleteProcess` для отслеживания прогресса.

**Метод:** PUT

**Тело запроса:**
```json
{
  "UserInfoDetail": {
    "employeeNo": "12345"
  }
}
```

**Примечание:** 
- Проверьте поддержку через `/ISAPI/AccessControl/capabilities` (должен быть `isSupportUserInfoDetailDelete: true`).
- При удалении пользователя также удаляется информация о связанных учетных данных (карта, отпечаток, фото лица, данные радужки).

---

#### 34. Удаление пользователя (DELETE метод)

**Endpoint:** `DELETE /ISAPI/AccessControl/UserInfo/Delete?format=json&employeeNo={employee_no}`

**Описание:** Альтернативный метод удаления пользователя через DELETE запрос.

**Метод:** DELETE

**Параметры:**
- `employeeNo` - ID сотрудника для удаления

---

#### 35. Прогресс удаления пользователя

**Endpoint:** `GET /ISAPI/AccessControl/UserInfoDetail/DeleteProcess`

**Описание:** Получение прогресса удаления информации о пользователе. Вызывайте этот API повторно для отслеживания прогресса удаления.

**Метод:** GET

**Ответ:** Информация о прогрессе удаления.

**Использование:** Вызывается после `/UserInfoDetail/Delete` для отслеживания статуса операции.

---

#### 36. Асинхронный импорт пользователей

**Endpoint:** `POST /ISAPI/AccessControl/UserInfo/asyncImportDatasTasks`

**Описание:** Запуск асинхронного импорта пользователей на устройство.

**Метод:** POST

**Тело запроса:**
```json
{
  "UserInfo": {
    "employeeNo": "12345",
    "name": "ImportTest"
  }
}
```

**Ответ:** ID задачи импорта.

---

#### 37. Статус задачи импорта

**Endpoint:** `GET /ISAPI/AccessControl/UserInfo/asyncImportDatasTasks/{task_id}/status?format=json`

**Описание:** Получение статуса задачи асинхронного импорта пользователей.

**Метод:** GET

**Параметры:**
- `task_id` - ID задачи импорта

**Ответ:** Статус задачи (в процессе, завершено, ошибка).

---

### Face Recognition (Распознавание лица)

#### 38. Режим распознавания лица

**Endpoint:** `GET /ISAPI/AccessControl/FaceRecognizeMode?format=json`

**Описание:** Получение текущего режима распознавания лица.

**Метод:** GET

**Ответ:**
```json
{
  "FaceRecognizeMode": {
    "mode": "normalMode"
  }
}
```

---

#### 39. Установка режима распознавания лица

**Endpoint:** `PUT /ISAPI/AccessControl/FaceRecognizeMode?format=json`

**Описание:** Установка режима распознавания лица.

**Метод:** PUT

**Тело запроса:**
```json
{
  "FaceRecognizeMode": {
    "mode": "normalMode"
  }
}
```

**Режимы:**
- `normalMode` - обычный режим
- Другие режимы в зависимости от модели устройства

---

#### 40. Захват фото лица

**Endpoint:** `POST /ISAPI/AccessControl/CaptureFaceData`

**Описание:** Запуск захвата фото лица с терминала. Устройство переходит в режим ожидания фото и возвращает URL захваченного изображения.

**Метод:** POST

**Тело запроса (form-urlencoded):**
```xml
<CaptureFaceDataCond version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">
  <captureInfrared>false</captureInfrared>
  <dataType>url</dataType>
</CaptureFaceDataCond>
```

**Ответ (XML):**
```xml
<CaptureFaceDataResponse>
  <faceURL>https://192.168.1.67/LOCALS/pic/web_face_enrollpic.jpg@WEB000000000020</faceURL>
</CaptureFaceDataResponse>
```

**Использование:** Используется перед регистрацией пользователя для получения фото с терминала.

---

### Remote Control & Verification (Удаленное управление и проверка)

#### 41. Возможности удаленного управления

**Endpoint:** `GET /ISAPI/AccessControl/RemoteControl/capabilities?format=json`

**Описание:** Получение информации о возможностях удаленного управления устройством.

**Метод:** GET

**Ответ:** Информация о поддерживаемых функциях удаленного управления.

---

#### 42. Запуск удаленной регистрации

**Endpoint:** `PUT /ISAPI/AccessControl/RemoteControl/register?format=json`

**Описание:** Запуск удаленной регистрации на терминале. Устройство переходит в режим ожидания регистрации пользователя.

**Метод:** PUT

**Тело запроса:**
```json
{
  "RemoteControl": {
    "cmd": "register",
    "employeeNo": "12345",
    "name": "Иван Иванов",
    "timeout": 60
  }
}
```

**Параметры:**
- `cmd` - команда ("register")
- `employeeNo` - ID сотрудника
- `name` - имя пользователя
- `timeout` - таймаут в секундах

---

#### 43. Конфигурация ACS

**Endpoint:** `GET /ISAPI/AccessControl/AcsCfg?format=json`

**Описание:** Получение конфигурации системы контроля доступа (ACS).

**Метод:** GET

---

#### 44. Установка конфигурации ACS

**Endpoint:** `PUT /ISAPI/AccessControl/AcsCfg?format=json`

**Описание:** Установка конфигурации системы контроля доступа. Используется для настройки параметров удаленной проверки: `remoteCheckDoorEnabled`, `checkChannelType`, `channelIp`, `needDeviceCheck`.

**Метод:** PUT

**Тело запроса:**
```json
{
  "AcsCfg": {
    "remoteCheckDoorEnabled": true,
    "checkChannelType": "http",
    "channelIp": "192.168.1.100",
    "needDeviceCheck": true
  }
}
```

---

#### 45. Удаленная проверка

**Endpoint:** `PUT /ISAPI/AccessControl/remoteCheck?format=json`

**Описание:** Применение результата удаленной проверки к устройству. Используется в сценариях с высокими требованиями безопасности, когда требуется проверка платформы перед открытием двери.

**Метод:** PUT

**Тело запроса:**
```json
{
  "remoteCheck": {
    "employeeNo": "12345",
    "result": "allow"
  }
}
```

**Сценарии использования:** Контроль пандемии, проверка поездок, проверка рисковых зон.

---

#### 46. Статус работы ACS

**Endpoint:** `GET /ISAPI/AccessControl/AcsWorkStatus?format=json`

**Описание:** Получение текущего статуса работы системы контроля доступа.

**Метод:** GET

**Ответ:** Информация о статусе работы ACS.

---

### Person & Card Comparison (Сравнение персоны и карты)

#### 47. Режим работы устройства

**Endpoint:** `GET /ISAPI/AccessControl/PersonAndCardComparison/DeviceWorkMode?format=json`

**Описание:** Получение режима работы устройства для сравнения персоны и карты.

**Метод:** GET

---

#### 48. Установка режима работы устройства

**Endpoint:** `PUT /ISAPI/AccessControl/PersonAndCardComparison/DeviceWorkMode?format=json`

**Описание:** Установка режима работы устройства для сравнения персоны и карты.

**Метод:** PUT

---

### Local Attendance (Локальная посещаемость)

#### 49. Поиск групп/департаментов

**Endpoint:** `POST /ISAPI/AccessControl/LocalAttendance/groupSearch?format=json`

**Описание:** Поиск групп/департаментов на устройстве.

**Метод:** POST

**Тело запроса:**
```json
{
  "GroupSearchCond": {
    "searchID": "uuid-string",
    "searchResultPosition": 0,
    "maxResults": 1000,
    "searchType": "all"
  }
}
```

**Ответ:**
```json
{
  "LocalAttendanceGroupSearch": {
    "Group": [
      {
        "groupId": 1,
        "groupName": "Отдел разработки",
        "groupNo": 1
      }
    ]
  }
}
```

**Использование:** Для получения списка департаментов при создании пользователя.

---

### User & Right Management (Управление пользователями и правами)

#### 50. Параметры управления паролями

**Endpoint:** `GET /ISAPI/AccessControl/UserAndRight/PwMgrParams?format=json`

**Описание:** Получение параметров управления паролями пользователей.

**Метод:** GET

---

#### 51. Возможности типов персонала

**Endpoint:** `GET /ISAPI/AccessControl/UserAndRight/CustomPersonnelType/capabilities?format=json`

**Описание:** Получение информации о возможностях работы с пользовательскими типами персонала.

**Метод:** GET

---

#### 52. Типы персонала

**Endpoint:** `GET /ISAPI/AccessControl/UserAndRight/CustomPersonnelType?format=json`

**Описание:** Получение списка пользовательских типов персонала.

**Метод:** GET

---

#### 53. Отображение пользователей и прав

**Endpoint:** `GET /ISAPI/AccessControl/userAndRightShow?format=json`

**Описание:** Получение информации для отображения пользователей и их прав доступа.

**Метод:** GET

---

### Permission Schedules (Расписания доступа)

#### 54. Шаблон расписания доступа

**Endpoint:** `GET /ISAPI/AccessControl/UserRightPlanTemplate/{planTemplateID}?format=json`

**Описание:** Получение шаблона расписания доступа для пользователей.

**Метод:** GET

**Параметры:**
- `planTemplateID` - ID шаблона расписания

**Примечание:** Проверьте поддержку через capabilities (`isSupportUserRightPlanTemplate: true`).

---

#### 55. Установка шаблона расписания доступа

**Endpoint:** `PUT /ISAPI/AccessControl/UserRightPlanTemplate/{planTemplateID}?format=json`

**Описание:** Установка или обновление шаблона расписания доступа.

**Метод:** PUT

**Параметры:**
- `planTemplateID` - ID шаблона расписания

**Примечание:** В каждом шаблоне можно добавить 1 недельное расписание и 4 группы праздников.

---

#### 56. Конфигурация группы праздников

**Endpoint:** `GET /ISAPI/AccessControl/UserRightHolidayGroupCfg/{holidayGroupID}?format=json`

**Описание:** Получение конфигурации группы праздников для расписания доступа.

**Метод:** GET

**Параметры:**
- `holidayGroupID` - ID группы праздников

**Примечание:** Проверьте поддержку через capabilities (`isSupportUserRightHolidayGroupCfg: true`).

---

#### 57. Установка группы праздников

**Endpoint:** `PUT /ISAPI/AccessControl/UserRightHolidayGroupCfg/{holidayGroupID}?format=json`

**Описание:** Установка или обновление конфигурации группы праздников.

**Метод:** PUT

**Параметры:**
- `holidayGroupID` - ID группы праздников

**Примечание:** Приоритет расписания праздников выше, чем недельного расписания.

---

### Anti-Passback (Антипассбэк)

#### 58. Правила сброса антипассбэка

**Endpoint:** `GET /ISAPI/AccessControl/AntiPassback/resetRules?format=json`

**Описание:** Получение правил сброса антипассбэка.

**Метод:** GET

**Примечание:** Проверьте поддержку через capabilities (`isSupportAntiPassbackResetRules: true`).

**Типы правил:**
1. Сброс по интервалу аутентификации
2. Сброс по времени
3. Недействительный режим (правила отключены)

---

#### 59. Установка правил сброса антипассбэка

**Endpoint:** `PUT /ISAPI/AccessControl/AntiPassback/resetRules?format=json`

**Описание:** Установка правил сброса антипассбэка.

**Метод:** PUT

**Примечание:** Антипассбэк по временному периоду и по времени не могут быть установлены одновременно.

---

### User Face (Фото пользователя)

#### 60. Получение фото лица пользователя

**Endpoint:** `GET /ISAPI/AccessControl/UserFace/faceData?...`

**Описание:** Получение фото лица пользователя с устройства.

**Метод:** GET

**Параметры:** Зависят от устройства, обычно включают `employeeNo` и другие параметры.

**Ответ:** Бинарные данные изображения (JPEG).

**Использование:** Для скачивания фото пользователя с терминала.

---

## Intelligent/FDLib (Библиотека лиц)

### Capabilities & Management

#### 61. Возможности FDLib

**Endpoint:** `GET /ISAPI/Intelligent/FDLib/capabilities?format=json`

**Описание:** Получение информации о возможностях библиотеки лиц (Face Detection Library).

**Метод:** GET

**Ответ:**
```json
{
  "FDLib": {
    "faceLibType": "blackFD",
    "maxFDID": 1,
    "maxFPID": 10000
  }
}
```

**Использование:** Для определения типа библиотеки (`blackFD`, `normalFD`) перед созданием записей.

---

#### 62. Список лиц из FDLib

**Endpoint:** `GET /ISAPI/Intelligent/FDLib?format=json`

**Описание:** Получение списка всех лиц в библиотеке FDLib.

**Метод:** GET

**Ответ:**
```json
{
  "statusCode": 1,
  "statusString": "OK",
  "FDLib": [
    {
      "FDID": "1",
      "faceLibType": "blackFD",
      "name": "mainlib"
    }
  ]
}
```

**Использование:** Для проверки существования FDLib перед добавлением лиц.

---

#### 63. Количество записей в FDLib

**Endpoint:** `GET /ISAPI/Intelligent/FDLib/Count?format=json`

**Описание:** Получение количества записей лиц в библиотеке FDLib.

**Метод:** GET

**Ответ:**
```json
{
  "FDLibCount": {
    "faceNumber": 150
  }
}
```

---

#### 64. Создание FDLib

**Endpoint:** `POST /ISAPI/Intelligent/FDLib/FDID?format=json`

**Описание:** Создание новой библиотеки лиц на устройстве.

**Метод:** POST

**Тело запроса:**
```json
{
  "FDID": "1",
  "faceLibType": "blackFD",
  "name": "mainlib"
}
```

**Параметры:**
- `FDID` - ID библиотеки (для DS-K1T343EFWX обычно "1")
- `faceLibType` - тип библиотеки ("blackFD" или "normalFD")
- `name` - имя библиотеки (латиница, без пробелов, ≤16 символов)

**Ответ:**
```json
{
  "statusCode": 1,
  "statusString": "OK"
}
```

---

#### 65. Удаление FDLib

**Endpoint:** `DELETE /ISAPI/Intelligent/FDLib/{fdid}`

**Описание:** Удаление библиотеки лиц с устройства.

**Метод:** DELETE

**Параметры:**
- `fdid` - ID библиотеки для удаления

**Внимание:** При удалении FDLib удаляются все записи лиц в этой библиотеке.

---

#### 66. Поиск лиц в FDLib

**Endpoint:** `POST /ISAPI/Intelligent/FDLib/FDSearch?format=json`

**Описание:** Поиск лиц в библиотеке FDLib.

**Метод:** POST

**Тело запроса:**
```json
{
  "FDSearchDescription": {
    "searchID": "1",
    "searchResultPosition": 0,
    "maxResults": 20
  }
}
```

**Ответ:** Список найденных лиц.

---

### Face Data Operations

#### 67. Добавление записи лица (JSON/Multipart)

**Endpoint:** `POST /ISAPI/Intelligent/FDLib/FaceDataRecord?format=json`

**Описание:** Добавление записи лица в библиотеку FDLib. Поддерживает два формата: multipart/form-data с бинарным изображением или JSON с base64.

**Метод:** POST

**Вариант 1: Multipart/form-data**
```
Content-Type: multipart/form-data

faceDataRecord: (file) face.jpg
faceLibType: blackFD
FDID: 1
FPID: 12345
name: Иван Иванов
sex: unknown
certificateType: ID
certificateNumber: 
bornTime: 
faceScore: 0
```

**Вариант 2: JSON с base64**
```json
{
  "FaceDataRecord": {
    "faceLibType": "blackFD",
    "FDID": "1",
    "FPID": "12345",
    "name": "Иван Иванов",
    "faceDataRecord": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
  }
}
```

**Ответ:**
```json
{
  "statusCode": 1,
  "statusString": "OK"
}
```

**Использование:** Рекомендуется использовать multipart/form-data для загрузки фото.

---

#### 68. Добавление записи лица (XML)

**Endpoint:** `POST /ISAPI/Intelligent/FDLib/FaceDataRecord`

**Описание:** Добавление записи лица в формате XML (fallback метод).

**Метод:** POST

**Content-Type:** `application/xml; charset=UTF-8`

**Тело запроса:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<FaceDataRecord>
  <faceLibType>blackFD</faceLibType>
  <FDID>1</FDID>
  <FPID>12345</FPID>
  <CaptureFaceDataCond>
    <faceLibType>blackFD</faceLibType>
    <FDID>1</FDID>
    <name>Иван Иванов</name>
    <sex>unknown</sex>
    <certificateType>ID</certificateType>
    <certificateNumber></certificateNumber>
    <bornTime></bornTime>
    <faceScore>0</faceScore>
    <faceDataRecord>data:image/jpeg;base64,...</faceDataRecord>
  </CaptureFaceDataCond>
</FaceDataRecord>
```

---

#### 69. Настройка FDLib для пользователя

**Endpoint:** `PUT /ISAPI/Intelligent/FDLib/FDSetUp?format=json&token={token}`

**Описание:** Настройка библиотеки лиц для пользователя. Используется после создания пользователя с фото для привязки лица к пользователю через faceURL.

**Метод:** PUT

**Параметры:**
- `token` - токен безопасности (полученный через `/ISAPI/Security/token`)

**Тело запроса (multipart/form-data):**
```
FaceDataRecord: {
  "faceLibType": "blackFD",
  "FDID": "1",
  "FPID": "12345",
  "faceURL": "https://192.168.1.67/LOCALS/pic/web_face_enrollpic.jpg@WEB000000000020"
}
```

**Ответ:**
```json
{
  "statusCode": 1,
  "statusString": "OK"
}
```

**Использование:** Используется после `CaptureFaceData` для привязки захваченного фото к пользователю.

---

#### 70. Загрузка фото пользователя (Multipart)

**Endpoint:** `POST /ISAPI/Intelligent/FDLib/pictureUpload?format=json`

**Описание:** Создание пользователя и загрузка фото в FDLib одним multipart-запросом.

**Метод:** POST

**Content-Type:** `multipart/form-data`

**Тело запроса:**
```
PictureUploadData: (XML)
<PictureUploadData>
  <faceLibType>blackFD</faceLibType>
  <FDID>1</FDID>
  <FPID>12345</FPID>
  <name>Иван Иванов</name>
  <groupId>1</groupId>
</PictureUploadData>

face_picture: (file) face.jpg
```

**Ответ:**
```json
{
  "statusCode": 1,
  "statusString": "OK"
}
```

**Использование:** Удобный метод для создания пользователя и загрузки фото одним запросом.

---

## Streaming (Потоковое видео)

### 71. Снимок с камеры

**Endpoint:** `GET /ISAPI/Streaming/channels/{channel_id}/picture`

**Описание:** Получение снимка с камеры терминала.

**Метод:** GET

**Параметры:**
- `channel_id` - номер канала (для терминалов обычно 101)

**Ответ:** Бинарные данные изображения (JPEG).

**Использование:** Для получения текущего снимка с камеры терминала.

---

## Event (События)

### 72. Подписка на события

**Endpoint:** `POST /ISAPI/Event/notification/subscribeEvent`

**Описание:** Подписка на события от устройства (события доступа, аутентификации и т.д.).

**Метод:** POST

**Content-Type:** `application/xml`

**Тело запроса:**
```xml
<EventNotification>
  <eventType>All</eventType>
</EventNotification>
```

**Ответ:** Подтверждение подписки.

**Использование:** Для получения событий в реальном времени от устройства.

---

### 73. Поток событий/алертов

**Endpoint:** `GET /ISAPI/Event/notification/alertStream`

**Описание:** Получение потока событий и алертов от устройства.

**Метод:** GET

**Ответ:** Поток событий (SSE или аналогичный).

**Использование:** Для мониторинга событий в реальном времени.

---

## Другие модули

### 74. Возможности потребления

**Endpoint:** `GET /ISAPI/Consume/capabilities?format=json`

**Описание:** Получение информации о возможностях модуля потребления (расходы, платежи и т.д.).

**Метод:** GET

---

### 75. Возможности умного шкафа

**Endpoint:** `GET /ISAPI/IntelligentCabinet/capabilities?format=json`

**Описание:** Получение информации о возможностях умного шкафа (если поддерживается).

**Метод:** GET

---

## Общие замечания

### Аутентификация

Все ISAPI endpoints используют **Digest Authentication** (RFC 2617). При каждом запросе необходимо передавать учетные данные пользователя.

**Пример (httpx):**
```python
auth = httpx.DigestAuth(username, password)
response = await client.get(url, auth=auth)
```

### Форматы данных

- **JSON:** Большинство endpoints поддерживают `?format=json`
- **XML:** Некоторые endpoints возвращают только XML
- **Multipart:** Используется для загрузки файлов (фото)

### Безопасность

- **Токен безопасности:** Некоторые операции требуют токен (`/ISAPI/Security/token`)
- **Шифрование:** Некоторые endpoints поддерживают `security=1&iv={iv}` для шифрования данных
- **SSL/TLS:** Рекомендуется использовать HTTPS (устройства часто имеют самоподписанные сертификаты)

### Проверка поддержки функций

Перед использованием endpoints рекомендуется проверять поддержку через соответствующие capabilities endpoints:

- `/ISAPI/AccessControl/capabilities` - общие возможности
- `/ISAPI/AccessControl/UserInfo/capabilities` - возможности UserInfo
- `/ISAPI/Intelligent/FDLib/capabilities` - возможности FDLib

### Коды ответов

- **200/201** - Успешное выполнение
- **400** - Ошибка в запросе (неверный формат данных)
- **401** - Неверные учетные данные
- **403** - Доступ запрещен (недостаточно прав)
- **404** - Endpoint не найден (не поддерживается устройством)
- **500** - Внутренняя ошибка устройства

### Статус коды в ответах

В JSON ответах часто используется структура:
```json
{
  "statusCode": 1,  // 1 = OK, другие значения = ошибка
  "statusString": "OK",
  "subStatusCode": "ok"
}
```

---

## Примеры использования

### Создание пользователя с фото

```python
# 1. Создать пользователя
POST /ISAPI/AccessControl/UserInfo/Record?format=json&security=1&iv={iv}
{
  "UserInfo": {
    "employeeNo": "12345",
    "name": "Иван Иванов",
    "userType": "normal"
  }
}

# 2. Загрузить фото
POST /ISAPI/Intelligent/FDLib/pictureUpload?format=json
(multipart/form-data с XML и фото)
```

### Захват фото с терминала

```python
# 1. Запустить захват
POST /ISAPI/AccessControl/CaptureFaceData
(xml: <CaptureFaceDataCond><dataType>url</dataType></CaptureFaceDataCond>)

# 2. Получить URL фото из ответа
# 3. Привязать к пользователю
PUT /ISAPI/Intelligent/FDLib/FDSetUp?format=json&token={token}
(с faceURL из шага 2)
```

### Поиск пользователей

```python
# 1. Получить количество
GET /ISAPI/AccessControl/UserInfo/Count?format=json

# 2. Поиск постранично
POST /ISAPI/AccessControl/UserInfo/Search?format=json
{
  "UserInfoSearchCond": {
    "searchID": "1",
    "searchResultPosition": 0,
    "maxResults": 30
  }
}
```

---

## Ссылки

- [Официальная документация Hikvision ISAPI](https://www.hikvision.com/en/support/download/sdk/)
- [Hikvision ISAPI Developer Guide](docs/ISAPI_Face Recognition Terminals_Value Series-111-125.pdf)
- [Postman Collection](docs/hikvision_full_isapi_collection.json)

---

**Примечание:** Этот документ основан на анализе кода проекта, документации Hikvision и реальных HTTP запросов. Некоторые endpoints могут отличаться в зависимости от модели устройства и версии прошивки. Всегда проверяйте capabilities endpoints перед использованием функций.

