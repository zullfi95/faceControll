"""
Простые unit тесты без зависимостей от конфигурации.
"""

import json
from datetime import datetime, time, timezone


def test_json_parsing():
    """Тест базового JSON парсинга."""
    test_data = {
        "AccessControllerEvent": {
            "employeeNoString": "1001",
            "eventType": "entry"
        }
    }

    json_str = json.dumps(test_data)
    parsed = json.loads(json_str)

    assert parsed["AccessControllerEvent"]["employeeNoString"] == "1001"
    assert parsed["AccessControllerEvent"]["eventType"] == "entry"
    print("✅ JSON parsing test passed")


def test_time_calculations():
    """Тест базовых расчетов времени."""
    # Простой расчет часов
    def calculate_hours_simple(start_hour, end_hour):
        return end_hour - start_hour

    result = calculate_hours_simple(10, 17)
    assert result == 7
    print("✅ Time calculation test passed")


def test_datetime_operations():
    """Тест операций с datetime."""
    dt1 = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    dt2 = datetime(2024, 1, 1, 17, 0, tzinfo=timezone.utc)

    diff = dt2 - dt1
    hours = diff.total_seconds() / 3600

    assert hours == 7.0
    print("✅ Datetime operations test passed")


if __name__ == "__main__":
    test_json_parsing()
    test_time_calculations()
    test_datetime_operations()
    print("🎉 All unit tests passed!")
