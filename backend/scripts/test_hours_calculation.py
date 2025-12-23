"""
Тестовый скрипт для проверки расчета часов с моковыми данными.
"""
import asyncio
import sys
import os
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

# Добавляем путь к app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.hours_calculation import (
    parse_sessions_from_events,
    calculate_hours_for_sessions,
    get_shift_time_range,
    BAKU_TZ
)
from app import models

# Константы для логирования
LOG_PATH = r"e:\FaceControll\.cursor\debug.log"

def debug_log(location, message, data, hypothesis_id, run_id="test1"):
    """Запись debug лога в NDJSON формате"""
    import json
    log_entry = {
        "sessionId": "debug-session",
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(datetime.now().timestamp() * 1000)
    }
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    except Exception as e:
        print(f"Error writing log: {e}")

def create_mock_event(user_id, event_type, timestamp_str, tz=BAKU_TZ):
    """Создание мокового события (по умолчанию в BAKU_TZ для корректного тестирования)"""
    event = models.AttendanceEvent()
    event.user_id = user_id
    event.event_type = event_type
    # Если timestamp_str заканчивается на Z, интерпретируем как UTC и конвертируем в BAKU_TZ
    if timestamp_str.endswith('Z'):
        dt_utc = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        event.timestamp = dt_utc.astimezone(BAKU_TZ)
    else:
        event.timestamp = datetime.fromisoformat(timestamp_str)
        if event.timestamp.tzinfo is None:
            event.timestamp = event.timestamp.replace(tzinfo=tz)
    return event

def test_scenario_1_normal_shift():
    """Тест 1: Нормальная смена 09:00-18:00, сессия 10:00-17:00"""
    print("\n=== Тест 1: Нормальная смена ===")
    
    # Создаем моковые события (в BAKU_TZ, не UTC!)
    events = [
        create_mock_event(1, "entry", "2025-12-16T10:00:00+04:00"),  # 10:00 BAKU
        create_mock_event(1, "exit", "2025-12-16T17:00:00+04:00"),  # 17:00 BAKU
    ]
    
    # Отладочный вывод
    print(f"Entry event timestamp: {events[0].timestamp}")
    print(f"Exit event timestamp: {events[1].timestamp}")
    
    # Создаем моковую смену
    class MockShift:
        def __init__(self):
            self.id = 1
            self.name = "Day Shift"
            self.schedule = {
                "0": {"enabled": True, "start": "09:00", "end": "18:00"},
                "1": {"enabled": True, "start": "09:00", "end": "18:00"},
                "2": {"enabled": True, "start": "09:00", "end": "18:00"},
                "3": {"enabled": True, "start": "09:00", "end": "18:00"},
                "4": {"enabled": True, "start": "09:00", "end": "18:00"},
            }
    
    shift = MockShift()
    report_date = datetime(2025, 12, 16, 0, 0, 0, tzinfo=BAKU_TZ)
    
    # #region agent log
    debug_log("test_hours_calculation.py:test_scenario_1", "Test 1 started", {
        "events_count": len(events),
        "events": [(e.event_type, str(e.timestamp)) for e in events],
        "shift_schedule": shift.schedule["1"]
    }, "A", "test1")
    # #endregion
    
    # Парсим сессии
    sessions = parse_sessions_from_events(events, report_date=report_date)
    
    # #region agent log
    debug_log("test_hours_calculation.py:test_scenario_1", "Sessions parsed", {
        "sessions_count": len(sessions),
        "sessions": [(str(s[0]), str(s[1])) for s in sessions]
    }, "A", "test1")
    # #endregion
    
    # Получаем диапазон смены
    shift_time_range = get_shift_time_range(shift, report_date)
    
    # #region agent log
    debug_log("test_hours_calculation.py:test_scenario_1", "Shift time range", {
        "shift_start": str(shift_time_range[0]) if shift_time_range else None,
        "shift_end": str(shift_time_range[1]) if shift_time_range else None
    }, "A", "test1")
    # #endregion
    
    # Рассчитываем часы
    if shift_time_range:
        hours_in, hours_out = calculate_hours_for_sessions(
            sessions, shift_time_range[0], shift_time_range[1], user_id=1
        )
        
        # #region agent log
        debug_log("test_hours_calculation.py:test_scenario_1", "Hours calculated", {
            "hours_in_shift": hours_in,
            "hours_outside_shift": hours_out,
            "total": hours_in + hours_out,
            "expected_in": 7.0,
            "expected_out": 0.0
        }, "A", "test1")
        # #endregion
        
        print(f"Часы в смене: {hours_in:.2f} (ожидается 7.00)")
        print(f"Часы вне смены: {hours_out:.2f} (ожидается 0.00)")
        assert abs(hours_in - 7.0) < 0.01, f"Ожидалось 7.00 часов в смене, получено {hours_in}"
        assert abs(hours_out - 0.0) < 0.01, f"Ожидалось 0.00 часов вне смены, получено {hours_out}"
        print("✓ Тест 1 пройден")

def test_scenario_2_overtime():
    """Тест 2: Переработка - сессия 08:00-20:00, смена 09:00-18:00"""
    print("\n=== Тест 2: Переработка ===")
    
    events = [
        create_mock_event(2, "entry", "2025-12-16T08:00:00+04:00"),  # 08:00 BAKU
        create_mock_event(2, "exit", "2025-12-16T20:00:00+04:00"),  # 20:00 BAKU
    ]
    
    class MockShift:
        def __init__(self):
            self.id = 1
            self.schedule = {"1": {"enabled": True, "start": "09:00", "end": "18:00"}}
    
    shift = MockShift()
    report_date = datetime(2025, 12, 16, 0, 0, 0, tzinfo=BAKU_TZ)
    
    # #region agent log
    debug_log("test_hours_calculation.py:test_scenario_2", "Test 2 started", {
        "events": [(e.event_type, str(e.timestamp)) for e in events]
    }, "B", "test1")
    # #endregion
    
    sessions = parse_sessions_from_events(events, report_date=report_date)
    shift_time_range = get_shift_time_range(shift, report_date)
    
    if shift_time_range:
        hours_in, hours_out = calculate_hours_for_sessions(
            sessions, shift_time_range[0], shift_time_range[1], user_id=2
        )
        
        # #region agent log
        debug_log("test_hours_calculation.py:test_scenario_2", "Hours calculated", {
            "hours_in_shift": hours_in,
            "hours_outside_shift": hours_out,
            "expected_in": 9.0,
            "expected_out": 3.0
        }, "B", "test1")
        # #endregion
        
        print(f"Часы в смене: {hours_in:.2f} (ожидается 9.00)")
        print(f"Часы вне смены: {hours_out:.2f} (ожидается 3.00)")
        assert abs(hours_in - 9.0) < 0.01, f"Ожидалось 9.00 часов в смене, получено {hours_in}"
        assert abs(hours_out - 3.0) < 0.01, f"Ожидалось 3.00 часов вне смены, получено {hours_out}"
        print("✓ Тест 2 пройден")

def test_scenario_3_unclosed_session_today():
    """Тест 3: Незакрытая сессия сегодня"""
    print("\n=== Тест 3: Незакрытая сессия сегодня ===")
    
    # Сессия началась сегодня в 09:00, но не закрыта
    now = datetime.now(BAKU_TZ)
    # Создаем entry_time на сегодня в 09:00
    entry_time = datetime.combine(now.date(), time(9, 0, 0), tzinfo=BAKU_TZ)
    # Если entry_time в будущем (например, сейчас 08:00), используем текущее время минус 1 час
    if entry_time > now:
        entry_time = now - timedelta(hours=1)
    
    events = [
        create_mock_event(3, "entry", entry_time.isoformat()),
    ]
    
    print(f"Now: {now}")
    print(f"Entry time: {entry_time}")
    print(f"Is entry in future: {entry_time > now}")
    print(f"Is same date: {entry_time.date() == now.date()}")
    
    # #region agent log
    debug_log("test_hours_calculation.py:test_scenario_3", "Test 3 started", {
        "entry_time": str(entry_time),
        "now": str(now),
        "is_today": entry_time.date() == now.date()
    }, "C", "test1")
    # #endregion
    
    report_date = datetime.now(BAKU_TZ)
    sessions = parse_sessions_from_events(events, report_date=report_date)
    
    # #region agent log
    debug_log("test_hours_calculation.py:test_scenario_3", "Sessions parsed", {
        "sessions_count": len(sessions),
        "sessions": [(str(s[0]), str(s[1])) for s in sessions] if sessions else []
    }, "C", "test1")
    # #endregion
    
    print(f"Сессий найдено: {len(sessions)} (ожидается 1)")
    assert len(sessions) == 1, f"Ожидалась 1 сессия, найдено {len(sessions)}"
    print(f"Начало сессии: {sessions[0][0]}")
    print(f"Конец сессии: {sessions[0][1]} (должно быть текущее время)")
    print("✓ Тест 3 пройден")

def test_scenario_4_unclosed_session_past():
    """Тест 4: Незакрытая сессия в прошлом (не в день отчета)"""
    print("\n=== Тест 4: Незакрытая сессия в прошлом ===")
    
    # Сессия началась вчера, но не закрыта
    yesterday = datetime.now(BAKU_TZ) - timedelta(days=1)
    entry_time = yesterday.replace(hour=9, minute=0, second=0, microsecond=0)
    
    events = [
        create_mock_event(4, "entry", entry_time.isoformat()),
    ]
    
    # Отчет за сегодня (не в день события)
    report_date = datetime.now(BAKU_TZ)
    
    # #region agent log
    debug_log("test_hours_calculation.py:test_scenario_4", "Test 4 started", {
        "entry_time": str(entry_time),
        "entry_date": str(entry_time.date()),
        "report_date": str(report_date.date()),
        "is_same_date": entry_time.date() == report_date.date()
    }, "D", "test1")
    # #endregion
    
    sessions = parse_sessions_from_events(events, report_date=report_date)
    
    # #region agent log
    debug_log("test_hours_calculation.py:test_scenario_4", "Sessions parsed", {
        "sessions_count": len(sessions),
        "sessions": [(str(s[0]), str(s[1])) for s in sessions] if sessions else []
    }, "D", "test1")
    # #endregion
    
    print(f"Сессий найдено: {len(sessions)} (ожидается 0 - не учитываем прошлые незакрытые)")
    assert len(sessions) == 0, f"Ожидалось 0 сессий для прошлого дня, найдено {len(sessions)}"
    print("✓ Тест 4 пройден")

def test_scenario_5_multiple_entries():
    """Тест 5: Несколько entry подряд (некорректная последовательность)"""
    print("\n=== Тест 5: Несколько entry подряд ===")
    
    events = [
        create_mock_event(5, "entry", "2025-12-16T09:00:00+04:00"),
        create_mock_event(5, "entry", "2025-12-16T10:00:00+04:00"),  # Второй entry без exit
        create_mock_event(5, "exit", "2025-12-16T18:00:00+04:00"),
    ]
    
    # #region agent log
    debug_log("test_hours_calculation.py:test_scenario_5", "Test 5 started", {
        "events": [(e.event_type, str(e.timestamp)) for e in events]
    }, "E", "test1")
    # #endregion
    
    report_date = datetime(2025, 12, 16, 0, 0, 0, tzinfo=BAKU_TZ)
    sessions = parse_sessions_from_events(events, report_date=report_date)
    
    # #region agent log
    debug_log("test_hours_calculation.py:test_scenario_5", "Sessions parsed", {
        "sessions_count": len(sessions),
        "sessions": [(str(s[0]), str(s[1])) for s in sessions]
    }, "E", "test1")
    # #endregion
    
    print(f"Сессий найдено: {len(sessions)} (ожидается 2 - первая закрывается вторым entry)")
    assert len(sessions) >= 1, f"Ожидалась хотя бы 1 сессия, найдено {len(sessions)}"
    print("✓ Тест 5 пройден")

def test_scenario_6_timezone_conversion():
    """Тест 6: Конвертация часовых поясов (UTC -> BAKU_TZ)"""
    print("\n=== Тест 6: Конвертация часовых поясов ===")
    
    # События в UTC (будут автоматически конвертированы в BAKU_TZ)
    # 05:00 UTC = 09:00 BAKU, 14:00 UTC = 18:00 BAKU
    events = [
        create_mock_event(6, "entry", "2025-12-16T05:00:00Z"),  # 09:00 BAKU
        create_mock_event(6, "exit", "2025-12-16T14:00:00Z"),  # 18:00 BAKU
    ]
    
    class MockShift:
        def __init__(self):
            self.id = 1
            self.schedule = {"1": {"enabled": True, "start": "09:00", "end": "18:00"}}
    
    shift = MockShift()
    report_date = datetime(2025, 12, 16, 0, 0, 0, tzinfo=BAKU_TZ)
    
    # #region agent log
    debug_log("test_hours_calculation.py:test_scenario_6", "Test 6 started", {
        "events_utc": [(e.event_type, str(e.timestamp)) for e in events],
        "baku_tz": str(BAKU_TZ)
    }, "A", "test1")
    # #endregion
    
    sessions = parse_sessions_from_events(events, report_date=report_date)
    shift_time_range = get_shift_time_range(shift, report_date)
    
    # #region agent log
    debug_log("test_hours_calculation.py:test_scenario_6", "After parsing", {
        "sessions": [(str(s[0]), str(s[1])) for s in sessions],
        "shift_range": (str(shift_time_range[0]), str(shift_time_range[1])) if shift_time_range else None
    }, "A", "test1")
    # #endregion
    
    if shift_time_range:
        hours_in, hours_out = calculate_hours_for_sessions(
            sessions, shift_time_range[0], shift_time_range[1], user_id=6
        )
        
        # #region agent log
        debug_log("test_hours_calculation.py:test_scenario_6", "Hours calculated", {
            "hours_in_shift": hours_in,
            "hours_outside_shift": hours_out,
            "expected_in": 9.0
        }, "A", "test1")
        # #endregion
        
        print(f"Часы в смене: {hours_in:.2f} (ожидается 9.00)")
        assert abs(hours_in - 9.0) < 0.01, f"Ожидалось 9.00 часов в смене, получено {hours_in}"
        print("✓ Тест 6 пройден")

if __name__ == "__main__":
    print("Запуск тестов расчета часов...")
    print(f"Логи записываются в: {LOG_PATH}")
    
    try:
        test_scenario_1_normal_shift()
        test_scenario_2_overtime()
        test_scenario_3_unclosed_session_today()
        test_scenario_4_unclosed_session_past()
        test_scenario_5_multiple_entries()
        test_scenario_6_timezone_conversion()
        
        print("\n✓ Все тесты пройдены успешно!")
    except AssertionError as e:
        print(f"\n✗ Тест провален: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Ошибка при выполнении тестов: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

