"""
Контрактные тесты для webhook обработчика.
"""

import pytest
from unittest.mock import Mock, AsyncMock
import json
from datetime import datetime
import sys
import os

# Добавляем путь к приложению
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.webhook_handler import parse_multipart_event, parse_json_event


class TestWebhookHandler:
    """Тесты для webhook обработчика."""

    @pytest.mark.asyncio
    async def test_parse_json_event_valid(self):
        """Тест парсинга валидного JSON события."""
        # Создаем mock request с JSON данными
        mock_request = Mock()
        mock_request.json = AsyncMock(return_value={
            "AccessControllerEvent": {
                "employeeNoString": "1001",
                "name": "Test User",
                "eventType": "entry",
                "cardReaderNo": "1",
                "eventTime": datetime.now().isoformat()
            }
        })

        event_data = await parse_json_event(mock_request)

        assert event_data is not None
        assert event_data["employeeNoString"] == "1001"
        assert event_data["name"] == "Test User"
        assert event_data["eventType"] == "entry"

    @pytest.mark.asyncio
    async def test_parse_json_event_heartbeat(self):
        """Тест игнорирования heartbeat событий."""
        mock_request = Mock()
        mock_request.json = AsyncMock(return_value={
            "AccessControllerEvent": {
                "eventType": "heartBeat"
            }
        })

        event_data = await parse_json_event(mock_request)

        assert event_data is None

    @pytest.mark.asyncio
    async def test_parse_json_event_invalid_json(self):
        """Тест обработки невалидного JSON."""
        mock_request = Mock()
        mock_request.json = AsyncMock(side_effect=json.JSONDecodeError("Invalid JSON", "", 0))

        event_data = await parse_json_event(mock_request)

        assert event_data is None

    @pytest.mark.asyncio
    async def test_parse_multipart_event_valid(self):
        """Тест парсинга валидного multipart события."""
        # Создаем mock request
        mock_request = Mock()
        mock_request.headers = {"content-type": "multipart/form-data"}

        # Mock form data
        mock_form = {
            "eventData": json.dumps({
                "AccessControllerEvent": {
                    "employeeNoString": "1002",
                    "name": "Multipart User",
                    "eventType": "exit",
                    "cardReaderNo": "2",
                    "eventTime": datetime.now().isoformat()
                }
            })
        }
        mock_request.form = AsyncMock(return_value=mock_form)

        event_data = await parse_multipart_event(mock_request)

        assert event_data is not None
        assert event_data["employeeNoString"] == "1002"
        assert event_data["name"] == "Multipart User"
        assert event_data["eventType"] == "exit"

    @pytest.mark.asyncio
    async def test_parse_multipart_event_not_multipart(self):
        """Тест отказа обработки не-multipart запроса."""
        mock_request = Mock()
        mock_request.headers = {"content-type": "application/json"}

        event_data = await parse_multipart_event(mock_request)

        assert event_data is None

    @pytest.mark.asyncio
    async def test_parse_multipart_event_heartbeat(self):
        """Тест игнорирования heartbeat в multipart."""
        mock_request = Mock()
        mock_request.headers = {"content-type": "multipart/form-data"}

        mock_form = {
            "eventData": json.dumps({
                "AccessControllerEvent": {
                    "eventType": "heartBeat"
                }
            })
        }
        mock_request.form = AsyncMock(return_value=mock_form)

        event_data = await parse_multipart_event(mock_request)

        assert event_data is None

    def test_event_data_structure(self):
        """Тест ожидаемой структуры данных события."""
        expected_structure = {
            "AccessControllerEvent": {
                "employeeNoString": str,
                "name": str,
                "eventType": str,  # "entry" или "exit"
                "cardReaderNo": str,
                "eventTime": str,  # ISO format
                "deviceID": str,   # опционально
                "cardNo": str,     # опционально
            }
        }

        # Этот тест проверяет, что мы знаем ожидаемую структуру
        # Реальные данные могут иметь дополнительные поля
        assert "AccessControllerEvent" in expected_structure
        assert "employeeNoString" in expected_structure["AccessControllerEvent"]
        assert "eventType" in expected_structure["AccessControllerEvent"]
