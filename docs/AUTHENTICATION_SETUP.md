# Настройка системы аутентификации

## Обзор

Система аутентификации использует JWT токены для защиты API endpoints. Доступ к странице управления пользователями системы (`/system-users`) имеют только пользователи с ролью **Operations Manager**.

## Первый запуск

### 1. Установка зависимостей

Зависимости уже добавлены в `requirements.txt`:
- `python-jose[cryptography]` - для JWT токенов
- `passlib[bcrypt]` - для хеширования паролей

Установите их:
```bash
docker-compose exec backend pip install -r requirements.txt
docker-compose restart backend
```

### 2. Создание первого пользователя

После установки зависимостей создайте первого пользователя Operations Manager через API:

```bash
# Сначала войдите (если пользователь уже создан)
curl -X POST "http://localhost/api/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"

# Или создайте пользователя через Python скрипт (если доступен)
docker-compose exec backend python scripts/create_admin_user.py
```

### 3. Создание пользователя через API (если нет доступа)

Если у вас нет пользователя, создайте его напрямую в БД:

```sql
-- Войдите в БД
docker-compose exec db psql -U postgres -d facerecog

-- Создайте пользователя (пароль: admin123)
-- Хеш пароля будет создан автоматически при первом входе через API
-- Или используйте Python для генерации хеша
```

## Использование

### Вход в систему

1. Откройте `/login` в браузере
2. Введите:
   - Username: `admin`
   - Password: `admin123` (или ваш пароль)

### Доступ к странице управления пользователями

После входа пользователь с ролью **Operations Manager** увидит в навигации пункт "Пользователи системы".

На этой странице доступны:
- Просмотр всех пользователей системы
- Создание нового пользователя
- Редактирование пользователя
- Удаление пользователя
- Назначение ролей

### Роли и доступ

- **Operations Manager** - полный доступ ко всем функциям управления пользователями
- Другие роли - доступ будет настроен позже

## API Endpoints

### Аутентификация

- `POST /api/auth/login` - Вход в систему
- `GET /api/auth/me` - Получение информации о текущем пользователе

### Управление пользователями (только Operations Manager)

- `GET /api/system-users/` - Список пользователей
- `POST /api/system-users/` - Создание пользователя
- `GET /api/system-users/{id}` - Получение пользователя
- `PUT /api/system-users/{id}` - Обновление пользователя
- `DELETE /api/system-users/{id}` - Удаление пользователя

## Безопасность

- Пароли хранятся в виде bcrypt хешей
- JWT токены действительны 30 дней
- Токены передаются в заголовке `Authorization: Bearer <token>`
- Все защищенные endpoints требуют валидный токен

## Troubleshooting

### Ошибка "ModuleNotFoundError: No module named 'passlib'"

Установите зависимости:
```bash
docker-compose exec backend pip install -r requirements.txt
docker-compose restart backend
```

### Ошибка 401 Unauthorized

Проверьте:
1. Токен не истек (30 дней)
2. Токен передается в заголовке `Authorization`
3. Пользователь активен (`is_active = true`)

### Ошибка 403 Forbidden

Убедитесь, что у пользователя роль `operations_manager`:
```sql
SELECT username, role FROM system_users;
```

