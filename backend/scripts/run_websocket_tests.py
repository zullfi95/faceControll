#!/usr/bin/env python3
"""
Запуск всех WebSocket тестов.
"""

import subprocess
import sys
import os
from pathlib import Path

# Add the parent directory to the path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.config import settings

def run_test(script_name, description):
    """Запуск одного тестового скрипта."""
    print(f"\n{'='*60}")
    print(f"[RUNNING] {description}")
    print('='*60)

    script_path = Path(__file__).parent / script_name

    if not script_path.exists():
        print(f"[ERROR] Test script {script_name} not found")
        return False

    try:
        result = subprocess.run([
            sys.executable, str(script_path)
        ], capture_output=True, text=True, timeout=300)

        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)

        success = result.returncode == 0
        status = "[PASSED]" if success else "[FAILED]"
        print(f"{status} {description} (exit code: {result.returncode})")

        return success

    except subprocess.TimeoutExpired:
        print(f"[TIMEOUT] {description} timed out")
        return False
    except Exception as e:
        print(f"[EXCEPTION] {description} failed with exception: {e}")
        return False

def clear_debug_logs():
    """Очистка debug логов перед запуском тестов."""
    log_path = settings.debug_log_path
    try:
        if os.path.exists(log_path):
            os.remove(log_path)
            print("[INFO] Cleared debug logs")
        else:
            print("[INFO] No debug logs to clear")
    except Exception as e:
        print(f"[WARNING] Failed to clear debug logs: {e}")

def main():
    """Основная функция."""
    print("[TEST SUITE] WebSocket Test Suite Runner")
    print("=" * 60)

    # Очистка логов перед запуском
    clear_debug_logs()

    # Список тестов для запуска
    tests = [
        ("test_websocket_manager.py", "Unit Tests for WebSocketManager"),
        ("test_websocket.py", "Integration Tests for WebSocket Connections"),
        ("test_websocket_frontend.py", "Frontend Simulation Tests"),
        ("test_websocket_load.py", "Load and Performance Tests")
    ]

    total_tests = len(tests)
    passed_tests = 0

    print(f"[INFO] Planned tests: {total_tests}")
    print()

    for script_name, description in tests:
        if run_test(script_name, description):
            passed_tests += 1

    # Итоговый отчет
    print(f"\n{'='*60}")
    print("[RESULTS] FINAL RESULTS")
    print('='*60)
    print(f"Tests passed: {passed_tests}/{total_tests}")

    if passed_tests == total_tests:
        print("[SUCCESS] ALL TESTS PASSED!")
        print("[SUCCESS] WebSocket functionality is working correctly")
        return 0
    else:
        print("[WARNING] SOME TESTS FAILED!")
        print("[INFO] Check the output above for details")
        return 1

if __name__ == "__main__":
    sys.exit(main())
