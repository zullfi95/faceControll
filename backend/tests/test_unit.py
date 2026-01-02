"""
Unit тесты для отдельных функций без зависимостей от БД и настроек.
"""

import pytest
from datetime import datetime, time, timezone
from unittest.mock import Mock, AsyncMock
import json


class TestHoursCalculation:
    """Тесты для функций расчета часов."""

    def test_calculate_work_hours_in_shift_basic(self):
        """Тест базового расчета часов в смене."""
        # Импортируем функцию напрямую
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "hours_calculation",
            "backend/app/utils/hours_calculation.py"
        )
        hours_calculation = importlib.util.module_from_spec(spec)

        # Mock зависимостей
        mock_timezone = Mock()
        mock_timezone.utc = timezone.utc

        hours_calculation.BAKU_TZ = timezone.utc

        # Выполняем код модуля
        spec.loader.exec_module(hours_calculation)

        # Тест
        shift_start = time(9, 0)
        shift_end = time(18, 0)
        shift_duration_hours = 9.0

        session_start = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        session_end = datetime(2024, 1, 1, 17, 0, tzinfo=timezone.utc)

        result = hours_calculation.calculate_work_hours_in_shift(
            session_start, session_end, shift_start, shift_end, shift_duration_hours
        )

        assert result == 7.0

    def test_calculate_work_hours_outside_shift(self):
        """Тест расчета часов вне смены."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "hours_calculation",
            "backend/app/utils/hours_calculation.py"
        )
        hours_calculation = importlib.util.module_from_spec(spec)
        hours_calculation.BAKU_TZ = timezone.utc
        spec.loader.exec_module(hours_calculation)

        shift_start = time(9, 0)
        shift_end = time(18, 0)

        session_start = datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc)
        session_end = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)

        result = hours_calculation.calculate_work_hours_outside_shift(
            session_start, session_end, shift_start, shift_end
        )

        assert result == 1.0  # 9:00 - 8:00 = 1 час


class TestWebhookHandler:
    """Тесты для webhook обработчика."""

    @pytest.mark.asyncio
    async def test_parse_json_event_valid(self):
        """Тест парсинга валидного JSON события."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "webhook_handler",
            "backend/app/webhook_handler.py"
        )
        webhook_handler = importlib.util.module_from_spec(spec)

        # Mock зависимостей
        webhook_handler.WEBHOOK_API_KEY = "test-key"

        spec.loader.exec_module(webhook_handler)

        # Создаем mock request
        mock_request = Mock()
        mock_request.json = AsyncMock(return_value={
            "AccessControllerEvent": {
                "employeeNoString": "1001",
                "name": "Test User",
                "eventType": "entry",
                "eventTime": "2024-01-01T09:00:00+04:00"
            }
        })

        result = await webhook_handler.parse_json_event(mock_request)

        assert result is not None
        assert result["employeeNoString"] == "1001"
        assert result["eventType"] == "entry"

    @pytest.mark.asyncio
    async def test_parse_json_event_heartbeat(self):
        """Тест игнорирования heartbeat событий."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "webhook_handler",
            "backend/app/webhook_handler.py"
        )
        webhook_handler = importlib.util.module_from_spec(spec)
        webhook_handler.WEBHOOK_API_KEY = "test-key"
        spec.loader.exec_module(webhook_handler)

        mock_request = Mock()
        mock_request.json = AsyncMock(return_value={
            "AccessControllerEvent": {
                "eventType": "heartBeat"
            }
        })

        result = await webhook_handler.parse_json_event(mock_request)

        assert result is None


class TestUtils:
    """Тесты для утилит."""

    def test_json_parsing(self):
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
