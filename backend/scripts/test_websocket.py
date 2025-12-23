#!/usr/bin/env python3
"""
Скрипт для тестирования WebSocket соединений с расширенной функциональностью.
"""

import asyncio
import websockets
import json
import sys
import time
from datetime import datetime

class WebSocketTester:
    """Класс для тестирования WebSocket соединений."""

    def __init__(self, base_url="ws://localhost"):
        self.base_url = base_url
        self.results = []

    def log_result(self, test_name, success, message="", details=None):
        """Логирование результатов теста."""
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
        self.results.append(result)

        status = "[PASS]" if success else "[FAIL]"
        print(f"{status} {test_name}: {message}")
        if details:
            for key, value in details.items():
                print(f"  {key}: {value}")

    async def test_basic_connection(self, endpoint):
        """Тестирование базового соединения."""
        url = f"{self.base_url}{endpoint}"
        try:
            async with websockets.connect(url) as websocket:
                # Отправляем начальное сообщение
                await websocket.send(json.dumps({"type": "connected"}))

                # Ждем подтверждения
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    response_data = json.loads(response)

                    if response_data.get("type") == "connected" and response_data.get("status") == "ok":
                        self.log_result("basic_connection", True, f"Successfully connected to {endpoint}")
                        return True
                    else:
                        self.log_result("basic_connection", False, f"Unexpected response: {response_data}", {"endpoint": endpoint})
                        return False

                except asyncio.TimeoutError:
                    self.log_result("basic_connection", False, "Timeout waiting for confirmation", {"endpoint": endpoint})
                    return False

        except Exception as e:
            self.log_result("basic_connection", False, f"Connection failed: {e}", {"endpoint": endpoint})
            return False

    async def test_message_exchange(self, endpoint):
        """Тестирование обмена сообщениями."""
        url = f"{self.base_url}{endpoint}"
        try:
            async with websockets.connect(url) as websocket:
                # Подключаемся
                await websocket.send(json.dumps({"type": "connected"}))

                # Игнорируем подтверждение
                try:
                    await asyncio.wait_for(websocket.recv(), timeout=2.0)
                except asyncio.TimeoutError:
                    pass

                # Тестируем отправку пользовательского сообщения
                test_message = {"type": "test", "data": {"test_id": 123}}
                await websocket.send(json.dumps(test_message))

                # Ждем эхо или подтверждения
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                    response_data = json.loads(response)

                    # Проверяем, что получили валидный JSON
                    if isinstance(response_data, dict):
                        self.log_result("message_exchange", True, f"Message exchange successful for {endpoint}")
                        return True
                    else:
                        self.log_result("message_exchange", False, "Invalid JSON response", {"endpoint": endpoint})
                        return False

                except asyncio.TimeoutError:
                    # Это нормально, если сервер не отвечает на тестовые сообщения
                    self.log_result("message_exchange", True, f"Message sent successfully (no response expected) for {endpoint}")
                    return True

        except Exception as e:
            self.log_result("message_exchange", False, f"Message exchange failed: {e}", {"endpoint": endpoint})
            return False

    async def test_connection_persistence(self, endpoint, duration=10):
        """Тестирование устойчивости соединения."""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()

        try:
            async with websockets.connect(url) as websocket:
                await websocket.send(json.dumps({"type": "connected"}))

                # Ждем подтверждения
                try:
                    await asyncio.wait_for(websocket.recv(), timeout=2.0)
                except asyncio.TimeoutError:
                    pass

                # Поддерживаем соединение в течение duration секунд
                ping_count = 0
                while time.time() - start_time < duration:
                    try:
                        # Отправляем ping каждые 2 секунды
                        await websocket.send(json.dumps({"type": "ping"}))
                        ping_count += 1

                        # Ждем pong или другого сообщения
                        try:
                            response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                            response_data = json.loads(response)

                            # Если получили ping, отвечаем pong
                            if response_data.get("type") == "ping":
                                await websocket.send(json.dumps({"type": "pong"}))

                        except asyncio.TimeoutError:
                            # Таймаут - это нормально для тестового сценария
                            pass

                        await asyncio.sleep(2)

                    except websockets.exceptions.ConnectionClosed:
                        elapsed = time.time() - start_time
                        self.log_result("connection_persistence", False,
                                      f"Connection closed prematurely after {elapsed:.1f}s",
                                      {"endpoint": endpoint, "duration": elapsed})
                        return False

                elapsed = time.time() - start_time
                self.log_result("connection_persistence", True,
                              f"Connection maintained for {elapsed:.1f}s",
                              {"endpoint": endpoint, "pings_sent": ping_count})
                return True

        except Exception as e:
            elapsed = time.time() - start_time
            self.log_result("connection_persistence", False,
                          f"Connection failed after {elapsed:.1f}s: {e}",
                          {"endpoint": endpoint, "duration": elapsed})
            return False

    async def test_multiple_connections(self, endpoint, count=3):
        """Тестирование множественных одновременных соединений."""
        url = f"{self.base_url}{endpoint}"
        connections = []

        try:
            # Создаем несколько соединений одновременно
            connect_tasks = []
            for i in range(count):
                task = asyncio.create_task(self._create_connection(url, i))
                connect_tasks.append(task)

            # Ждем завершения всех подключений
            results = await asyncio.gather(*connect_tasks, return_exceptions=True)

            successful_connections = sum(1 for r in results if r is True)
            failed_connections = sum(1 for r in results if isinstance(r, Exception) or r is False)

            if successful_connections == count:
                self.log_result("multiple_connections", True,
                              f"All {count} connections successful for {endpoint}")
                return True
            else:
                self.log_result("multiple_connections", False,
                              f"Only {successful_connections}/{count} connections successful for {endpoint}",
                              {"successful": successful_connections, "failed": failed_connections})
                return False

        except Exception as e:
            self.log_result("multiple_connections", False,
                          f"Multiple connections test failed: {e}",
                          {"endpoint": endpoint, "count": count})
            return False
        finally:
            # Закрываем все соединения
            for conn in connections:
                try:
                    await conn.close()
                except:
                    pass

    async def _create_connection(self, url, connection_id):
        """Создание одного соединения для теста множественных подключений."""
        try:
            async with websockets.connect(url) as websocket:
                await websocket.send(json.dumps({"type": "connected"}))

                # Ждем подтверждения
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                    response_data = json.loads(response)

                    if response_data.get("type") == "connected":
                        return True
                    else:
                        return False
                except asyncio.TimeoutError:
                    return False

        except Exception:
            return False

    async def test_server_unavailable(self, endpoint):
        """Тестирование поведения при недоступности сервера."""
        # Используем несуществующий порт
        url = f"ws://localhost:9999{endpoint}"

        try:
            async with websockets.connect(url) as websocket:
                self.log_result("server_unavailable", False,
                              "Unexpectedly connected to unavailable server",
                              {"endpoint": endpoint})
                return False

        except (websockets.exceptions.InvalidURI,
                websockets.exceptions.ConnectionClosed,
                OSError) as e:
            # Это ожидаемое поведение
            self.log_result("server_unavailable", True,
                          f"Correctly failed to connect to unavailable server: {type(e).__name__}",
                          {"endpoint": endpoint})
            return True
        except Exception as e:
            self.log_result("server_unavailable", False,
                          f"Unexpected error when connecting to unavailable server: {e}",
                          {"endpoint": endpoint})
            return False

    async def run_all_tests(self, endpoints):
        """Запуск всех тестов для заданных эндпоинтов."""
        print("[TEST SUITE] WebSocket Testing Suite")
        print("=" * 50)

        total_tests = 0
        passed_tests = 0

        for endpoint in endpoints:
            print(f"\n[ENDPOINT] Testing endpoint: {endpoint}")
            print("-" * 30)

            # Базовое соединение
            if await self.test_basic_connection(endpoint):
                passed_tests += 1
            total_tests += 1

            # Обмен сообщениями
            if await self.test_message_exchange(endpoint):
                passed_tests += 1
            total_tests += 1

            # Устойчивость соединения
            if await self.test_connection_persistence(endpoint, duration=5):
                passed_tests += 1
            total_tests += 1

        # Тест множественных соединений (только для первого эндпоинта)
        if endpoints:
            if await self.test_multiple_connections(endpoints[0], count=3):
                passed_tests += 1
            total_tests += 1

        # Тест недоступного сервера
        if await self.test_server_unavailable(endpoints[0] if endpoints else "/api/ws/test"):
            passed_tests += 1
        total_tests += 1

        # Итоговый отчет
        print(f"\n[RESULTS] Test Results: {passed_tests}/{total_tests} tests passed")

        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        print(f"Success rate: {success_rate:.1f}%")
        return passed_tests == total_tests

async def main():
    """Основная функция."""
    # Проверяем аргументы командной строки
    base_url = "ws://localhost"
    if len(sys.argv) > 1:
        base_url = sys.argv[1]

    # Эндпоинты для тестирования
    endpoints = [
        "/api/ws/events",
        "/api/ws/reports",
        "/api/ws/dashboard"
    ]

    tester = WebSocketTester(base_url)
    success = await tester.run_all_tests(endpoints)

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())









