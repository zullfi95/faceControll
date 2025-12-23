#!/usr/bin/env python3
"""
Unit tests for WebSocketManager class.
"""

import asyncio
import json
import sys
import inspect
from datetime import datetime

# Add the app directory to the path
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.utils.websocket_manager import WebSocketManager


class MockWebSocket:
    """Mock WebSocket for testing."""

    def __init__(self, should_fail_send=False, should_fail_accept=False):
        self.should_fail_send = should_fail_send
        self.should_fail_accept = should_fail_accept
        self.sent_messages = []
        self.accepted = False
        self.closed = False

    async def accept(self):
        if self.should_fail_accept:
            raise Exception("Mock accept failure")
        self.accepted = True

    async def send_json(self, message):
        if self.should_fail_send:
            raise Exception("Mock send failure")
        self.sent_messages.append(message)

    async def close(self):
        self.closed = True


class TestWebSocketManager:
    """Test suite for WebSocketManager."""

    def setup_method(self):
        """Setup before each test."""
        self.manager = WebSocketManager()

    def teardown_method(self):
        """Cleanup after each test."""
        # Reset the global instance
        self.manager.active_connections = {
            "events": [],
            "reports": [],
            "dashboard": []
        }

    async def test_initialization(self):
        """Test WebSocketManager initialization."""
        assert isinstance(self.manager.active_connections, dict)
        assert "events" in self.manager.active_connections
        assert "reports" in self.manager.active_connections
        assert "dashboard" in self.manager.active_connections
        assert len(self.manager.active_connections["events"]) == 0

    async def test_connect_success(self):
        """Test successful WebSocket connection."""
        ws = MockWebSocket()
        await self.manager.connect(ws, "events")

        assert ws.accepted
        assert ws in self.manager.active_connections["events"]
        assert len(self.manager.active_connections["events"]) == 1

    async def test_connect_new_channel(self):
        """Test connection to a new channel."""
        ws = MockWebSocket()
        await self.manager.connect(ws, "custom_channel")

        assert ws.accepted
        assert "custom_channel" in self.manager.active_connections
        assert ws in self.manager.active_connections["custom_channel"]

    async def test_connect_accept_failure(self):
        """Test connection failure during accept."""
        ws = MockWebSocket(should_fail_accept=True)

        try:
            await self.manager.connect(ws, "events")
            assert False, "Should have raised an exception"
        except Exception as e:
            assert "Mock accept failure" in str(e)

        # WebSocket should not be added to connections
        assert ws not in self.manager.active_connections["events"]

    async def test_disconnect_existing_connection(self):
        """Test disconnecting an existing connection."""
        ws = MockWebSocket()
        await self.manager.connect(ws, "events")

        assert len(self.manager.active_connections["events"]) == 1

        await self.manager.disconnect(ws, "events")

        assert ws not in self.manager.active_connections["events"]
        assert len(self.manager.active_connections["events"]) == 0

    async def test_disconnect_nonexistent_connection(self):
        """Test disconnecting a non-existent connection."""
        ws = MockWebSocket()
        # Don't connect first

        # Should not raise an exception
        await self.manager.disconnect(ws, "events")

        # Connections should remain unchanged
        assert len(self.manager.active_connections["events"]) == 0

    async def test_disconnect_from_wrong_channel(self):
        """Test disconnecting from wrong channel."""
        ws = MockWebSocket()
        await self.manager.connect(ws, "events")

        # Try to disconnect from reports channel
        await self.manager.disconnect(ws, "reports")

        # Should still be in events channel
        assert ws in self.manager.active_connections["events"]

    async def test_broadcast_success(self):
        """Test successful broadcast to multiple connections."""
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        await self.manager.connect(ws1, "events")
        await self.manager.connect(ws2, "events")

        message = {"type": "test", "data": "hello"}
        await self.manager.broadcast(message, "events")

        assert len(ws1.sent_messages) == 1
        assert len(ws2.sent_messages) == 1
        assert ws1.sent_messages[0] == message
        assert ws2.sent_messages[0] == message

    async def test_broadcast_with_failed_connections(self):
        """Test broadcast when some connections fail."""
        ws1 = MockWebSocket()  # Will succeed
        ws2 = MockWebSocket(should_fail_send=True)  # Will fail
        ws3 = MockWebSocket()  # Will succeed

        await self.manager.connect(ws1, "events")
        await self.manager.connect(ws2, "events")
        await self.manager.connect(ws3, "events")

        message = {"type": "test", "data": "hello"}
        await self.manager.broadcast(message, "events")

        # Successful connections should receive the message
        assert len(ws1.sent_messages) == 1
        assert len(ws3.sent_messages) == 1
        assert ws1.sent_messages[0] == message
        assert ws3.sent_messages[0] == message

        # Failed connection should be removed
        assert ws2 not in self.manager.active_connections["events"]
        assert len(self.manager.active_connections["events"]) == 2

    async def test_broadcast_nonexistent_channel(self):
        """Test broadcast to non-existent channel."""
        message = {"type": "test", "data": "hello"}
        # Should not raise an exception
        await self.manager.broadcast(message, "nonexistent")

    async def test_notify_event_update(self):
        """Test event update notification."""
        ws = MockWebSocket()
        await self.manager.connect(ws, "events")

        event_data = {"event_id": 123, "user_id": 456}
        await self.manager.notify_event_update(event_data)

        assert len(ws.sent_messages) == 1
        message = ws.sent_messages[0]

        assert message["type"] == "event_update"
        assert "timestamp" in message
        assert message["data"] == event_data

        # Verify timestamp is valid ISO format
        datetime.fromisoformat(message["timestamp"])

    async def test_notify_report_update(self):
        """Test report update notification."""
        ws = MockWebSocket()
        await self.manager.connect(ws, "reports")

        report_data = {"report_id": 789, "status": "completed"}
        await self.manager.notify_report_update(report_data)

        assert len(ws.sent_messages) == 1
        message = ws.sent_messages[0]

        assert message["type"] == "report_update"
        assert "timestamp" in message
        assert message["data"] == report_data

    async def test_notify_dashboard_update(self):
        """Test dashboard update notification."""
        ws = MockWebSocket()
        await self.manager.connect(ws, "dashboard")

        dashboard_data = {"total_events": 100, "active_users": 50}
        await self.manager.notify_dashboard_update(dashboard_data)

        assert len(ws.sent_messages) == 1
        message = ws.sent_messages[0]

        assert message["type"] == "dashboard_update"
        assert "timestamp" in message
        assert message["data"] == dashboard_data

    def test_get_connection_count_single_channel(self):
        """Test getting connection count for a single channel."""
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()

        # Add connections manually (since connect is async)
        self.manager.active_connections["events"].extend([ws1, ws2])

        assert self.manager.get_connection_count("events") == 2
        assert self.manager.get_connection_count("reports") == 0

    def test_get_connection_count_all_channels(self):
        """Test getting total connection count across all channels."""
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        ws3 = MockWebSocket()

        # Add connections manually
        self.manager.active_connections["events"].extend([ws1, ws2])
        self.manager.active_connections["reports"].append(ws3)

        assert self.manager.get_connection_count() == 3

    async def test_concurrent_connections(self):
        """Test multiple concurrent connections."""
        # Create multiple connections simultaneously
        connections = []
        for i in range(10):
            ws = MockWebSocket()
            connections.append(ws)

        # Connect all concurrently
        await asyncio.gather(*[
            self.manager.connect(ws, "events") for ws in connections
        ])

        assert len(self.manager.active_connections["events"]) == 10

    async def test_concurrent_broadcast(self):
        """Test concurrent broadcasts."""
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        await self.manager.connect(ws1, "events")
        await self.manager.connect(ws2, "events")

        # Send multiple broadcasts concurrently
        messages = [
            {"type": "msg1", "data": "test1"},
            {"type": "msg2", "data": "test2"},
            {"type": "msg3", "data": "test3"}
        ]

        await asyncio.gather(*[
            self.manager.broadcast(msg, "events") for msg in messages
        ])

        # Each connection should receive all messages
        assert len(ws1.sent_messages) == 3
        assert len(ws2.sent_messages) == 3
        assert ws1.sent_messages == messages
        assert ws2.sent_messages == messages


async def run_tests():
    """Run all tests manually."""
    test_instance = TestWebSocketManager()
    test_methods = [method for method in dir(test_instance) if method.startswith('test_')]

    passed = 0
    failed = 0

    for test_method in test_methods:
        try:
            print(f"Running {test_method}...")
            test_instance.setup_method()

            if inspect.iscoroutinefunction(getattr(test_instance, test_method)):
                await getattr(test_instance, test_method)()
            else:
                getattr(test_instance, test_method)()

            test_instance.teardown_method()
            print(f"[PASS] {test_method}")
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test_method}: {e}")
            failed += 1

    print(f"\nTest Results: {passed} passed, {failed} failed")
    return failed == 0

if __name__ == "__main__":
    # Run the tests
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
