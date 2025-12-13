# Система ролей и вход/выход с одного терминала

## Система ролей

Система поддерживает 5 ролей пользователей:

1. **Project Lead** (`project_lead`) - Высший уровень управления
2. **Operations Manager** (`operations_manager`) - Управление операциями
3. **Manager** (`manager`) - Менеджер
4. **Supervisor** (`supervisor`) - Супервайзер
5. **Cleaner** (`cleaner`) - Уборщик (роль по умолчанию)

### API Endpoints

#### Получение списка ролей

**Endpoint:** `GET /api/roles`

**Описание:** Возвращает список всех доступных ролей в системе.

**Пример запроса:**
```bash
curl -X GET http://localhost/api/roles
```

**Пример ответа:**
```json
{
  "roles": [
    {
      "value": "project_lead",
      "display_name": "Project Lead"
    },
    {
      "value": "operations_manager",
      "display_name": "Operations Manager"
    },
    {
      "value": "manager",
      "display_name": "Manager"
    },
    {
      "value": "supervisor",
      "display_name": "Supervisor"
    },
    {
      "value": "cleaner",
      "display_name": "Cleaner"
    }
  ]
}
```

#### Создание пользователя с ролью

**Endpoint:** `POST /api/users/`

**Тело запроса:**
```json
{
  "hikvision_id": "1001",
  "full_name": "Иван Иванов",
  "department": "IT",
  "role": "manager"
}
```

**Параметры:**
- `role` (опционально) - Роль пользователя. Если не указана, используется `cleaner` по умолчанию.

#### Обновление роли пользователя

**Endpoint:** `PUT /api/users/{user_id}`

**Тело запроса:**
```json
{
  "role": "operations_manager"
}
```

### Миграция базы данных

Для добавления поля `role` в таблицу `users` выполните миграцию:

```bash
# Через docker-compose
docker-compose exec db psql -U postgres -d facerecog -f /app/migrations/002_add_user_role.sql

# Или напрямую
psql -U postgres -d facerecog -f backend/migrations/002_add_user_role.sql
```

Миграция:
- Добавляет поле `role` в таблицу `users`
- Устанавливает значение по умолчанию `cleaner` для существующих пользователей
- Создает индекс для оптимизации запросов по ролям

## Система вход/выход с одного терминала

Система автоматически определяет, является ли событие входом или выходом на основе предыдущих событий пользователя на том же терминале.

### Логика работы

1. **Первое событие пользователя** - всегда считается **входом** (`entry`)
2. **Последующее событие:**
   - Если последнее событие было **входом** (`entry`) → следующее будет **выходом** (`exit`)
   - Если последнее событие было **выходом** (`exit`) → следующее будет **входом** (`entry`)

### Пример работы

```
Пользователь: Иван Иванов (ID: 1001)
Терминал: 192.168.1.67

Событие 1 (10:00) - Первое событие → entry (вход)
Событие 2 (12:00) - Последнее было entry → exit (выход)
Событие 3 (13:00) - Последнее было exit → entry (вход)
Событие 4 (18:00) - Последнее было entry → exit (выход)
```

### Реализация

Логика реализована в модуле `backend/app/utils/entry_exit.py`:

```python
from backend.app.utils.entry_exit import determine_entry_exit

# Определение типа события
event_type = await determine_entry_exit(
    db=db,
    user_id=user.id,
    employee_no=event.employee_no,
    terminal_ip=event.terminal_ip,
    timestamp=event.timestamp
)
```

### Интеграция

Логика определения входа/выхода интегрирована в обработку событий:

1. **При получении события через webhook** - тип события определяется автоматически
2. **При синхронизации событий с терминала** - тип события определяется на основе предыдущих событий
3. **При создании события вручную** - можно указать тип явно или использовать автоматическое определение

### Важные замечания

- Логика работает **для каждого терминала отдельно** - события на разных терминалах не влияют друг на друга
- Определение основано на **последнем событии пользователя на конкретном терминале**
- Если у пользователя нет предыдущих событий, первое событие всегда считается входом
- Тип события сохраняется в поле `event_type` таблицы `attendance_events`

## Использование в коде

### Получение роли пользователя

```python
from backend.app.enums import UserRole

user = await crud.get_user_by_id(db, user_id)
role = UserRole(user.role) if user.role else UserRole.CLEANER
display_name = UserRole.get_display_name(role)
```

### Проверка роли

```python
from backend.app.enums import UserRole

if user.role == UserRole.MANAGER.value:
    # Логика для менеджера
    pass
```

### Получение всех ролей

```python
from backend.app.enums import UserRole

all_roles = UserRole.get_all_roles()
# Возвращает: [("project_lead", "Project Lead"), ...]
```

## Будущие улучшения

В будущем планируется:

1. **Система прав доступа** - привязка функционала к ролям
2. **Фильтрация по ролям** - отображение пользователей по ролям
3. **Статистика по ролям** - отчеты по входам/выходам для каждой роли
4. **Настройка логики входа/выхода** - возможность настройки правил определения

