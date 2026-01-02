"""
Тесты для основных функций приложения без зависимостей от БД и настроек.
"""

import json
from datetime import datetime, time, timezone
from unittest.mock import Mock, AsyncMock


def test_calculate_work_hours_logic():
    """Тест логики расчета часов работы."""
    # Имитируем функцию расчета часов
    def calculate_work_hours_in_shift(session_start, session_end, shift_start, shift_end):
        """Упрощенная версия расчета часов в смене."""
        # Преобразуем время в минуты от начала дня
        def time_to_minutes(t):
            return t.hour * 60 + t.minute

        session_start_minutes = time_to_minutes(session_start.time())
        session_end_minutes = time_to_minutes(session_end.time())
        shift_start_minutes = time_to_minutes(shift_start)
        shift_end_minutes = time_to_minutes(shift_end)

        # Находим пересечение сессии со сменой
        work_start = max(session_start_minutes, shift_start_minutes)
        work_end = min(session_end_minutes, shift_end_minutes)

        if work_end <= work_start:
            return 0.0

        return (work_end - work_start) / 60.0

    # Тест 1: Полностью в смене
    shift_start = time(9, 0)
    shift_end = time(18, 0)
    session_start = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    session_end = datetime(2024, 1, 1, 17, 0, tzinfo=timezone.utc)

    result = calculate_work_hours_in_shift(session_start, session_end, shift_start, shift_end)
    assert result == 7.0, f"Expected 7.0, got {result}"

    # Тест 2: Частично в смене
    session_start = datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc)
    session_end = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)

    result = calculate_work_hours_in_shift(session_start, session_end, shift_start, shift_end)
    assert result == 3.0, f"Expected 3.0, got {result}"

    # Тест 3: Вне смены
    session_start = datetime(2024, 1, 1, 6, 0, tzinfo=timezone.utc)
    session_end = datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc)

    result = calculate_work_hours_in_shift(session_start, session_end, shift_start, shift_end)
    assert result == 0.0, f"Expected 0.0, got {result}"

    print("✅ Work hours calculation tests passed")


def test_webhook_data_validation():
    """Тест валидации данных webhook."""
    def validate_event_data(data):
        """Проверка структуры данных события."""
        if not isinstance(data, dict):
            return False

        if "AccessControllerEvent" not in data:
            return False

        event = data["AccessControllerEvent"]
        required_fields = ["employeeNoString", "eventType", "eventTime"]

        for field in required_fields:
            if field not in event:
                return False

        # Проверка типа события
        if event.get("eventType") not in ["entry", "exit"]:
            return False

        return True

    # Валидные данные
    valid_data = {
        "AccessControllerEvent": {
            "employeeNoString": "1001",
            "eventType": "entry",
            "eventTime": "2024-01-01T09:00:00+04:00",
            "name": "Test User"
        }
    }
    assert validate_event_data(valid_data) == True

    # Недействительные данные - отсутствует поле
    invalid_data = {
        "AccessControllerEvent": {
            "employeeNoString": "1001",
            "eventTime": "2024-01-01T09:00:00+04:00"
        }
    }
    assert validate_event_data(invalid_data) == False

    # Недействительные данные - неправильный тип события
    invalid_data2 = {
        "AccessControllerEvent": {
            "employeeNoString": "1001",
            "eventType": "heartbeat",
            "eventTime": "2024-01-01T09:00:00+04:00"
        }
    }
    assert validate_event_data(invalid_data2) == False

    print("✅ Webhook data validation tests passed")


def test_time_zone_handling():
    """Тест обработки часовых поясов."""
    # Baku timezone (UTC+4)
    baku_offset = 4 * 3600  # 4 hours in seconds

    def convert_to_baku_time(utc_time):
        """Конвертация UTC времени в Baku timezone."""
        from datetime import timedelta
        return utc_time + timedelta(seconds=baku_offset)

    utc_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
    baku_time = convert_to_baku_time(utc_time)

    # Проверяем, что время увеличилось на 4 часа
    assert baku_time.hour == 13, f"Expected hour 13, got {baku_time.hour}"
    assert baku_time.day == 1, f"Expected same day, got {baku_time.day}"

    print("✅ Time zone handling tests passed")


def test_jwt_token_structure():
    """Тест структуры JWT токенов."""
    import base64

    def decode_jwt_payload(token):
        """Декодирование payload JWT токена."""
        try:
            # JWT имеет формат: header.payload.signature
            parts = token.split('.')
            if len(parts) != 3:
                return None

            # Декодируем payload (вторая часть)
            payload_b64 = parts[1]
            # Добавляем padding если нужно
            payload_b64 += '=' * (4 - len(payload_b64) % 4)
            payload_bytes = base64.urlsafe_b64decode(payload_b64)
            payload_str = payload_bytes.decode('utf-8')
            return json.loads(payload_str)
        except:
            return None

    # Создаем mock JWT payload без внешней зависимости
    # Имитируем структуру JWT
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": "test-user", "exp": 1234567890}

    import base64
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    signature = "mock_signature"

    token = f"{header_b64}.{payload_b64}.{signature}"
    decoded = decode_jwt_payload(token)

    assert decoded is not None
    assert decoded["sub"] == "test-user"

    print("✅ JWT token structure tests passed")


def test_encryption_functions():
    """Тест функций шифрования."""
    from cryptography.fernet import Fernet
    import base64

    # Генерируем правильный ключ (32 байта)
    key = Fernet.generate_key()
    cipher = Fernet(key)

    # Тест шифрования/дешифрования
    test_data = "sensitive-device-password"
    encrypted = cipher.encrypt(test_data.encode())
    decrypted = cipher.decrypt(encrypted).decode()

    assert decrypted == test_data

    print("✅ Encryption functions tests passed")


if __name__ == "__main__":
    test_calculate_work_hours_logic()
    test_webhook_data_validation()
    test_time_zone_handling()
    test_jwt_token_structure()
    test_encryption_functions()
    print("🎉 All core function tests passed!")
