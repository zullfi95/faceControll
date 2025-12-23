"""
Тестовый скрипт для проверки расчета часов с реальными данными из БД.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, time, timedelta

# Добавляем путь к app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal
from app import crud, models
from app.utils.hours_calculation import (
    parse_sessions_from_events,
    calculate_hours_for_sessions,
    get_shift_time_range,
    get_user_shift_for_date,
    BAKU_TZ
)

async def test_real_data():
    """Тест с реальными данными из БД"""
    print("=" * 60)
    print("Тестирование расчета часов с реальными данными из БД")
    print("=" * 60)
    
    async with AsyncSessionLocal() as db:
        try:
            # Получаем последние события
            events_result = await crud.get_events(db, limit=100)
            events, total = events_result
            
            print(f"\nНайдено событий в БД: {total}")
            
            if not events:
                print("⚠ Нет событий в БД для тестирования")
                return
            
            # Группируем события по пользователям
            user_events = {}
            for event in events:
                if event.user_id:
                    if event.user_id not in user_events:
                        user_events[event.user_id] = []
                    user_events[event.user_id].append(event)
            
            print(f"Пользователей с событиями: {len(user_events)}")
            
            # Тестируем для первых 3 пользователей
            tested_users = 0
            for user_id, user_events_list in list(user_events.items())[:3]:
                tested_users += 1
                print(f"\n--- Пользователь ID {user_id} ---")
                
                # Получаем пользователя
                user = await crud.get_user_by_id(db, user_id)
                if not user:
                    print(f"  ⚠ Пользователь {user_id} не найден")
                    continue
                
                print(f"  Имя: {user.full_name or f'User {user.hikvision_id}'}")
                print(f"  Событий: {len(user_events_list)}")
                
                # Сортируем события по времени
                sorted_events = sorted(user_events_list, key=lambda x: x.timestamp)
                print(f"  Первое событие: {sorted_events[0].timestamp} ({sorted_events[0].event_type})")
                print(f"  Последнее событие: {sorted_events[-1].timestamp} ({sorted_events[-1].event_type})")
                
                # Парсим сессии
                report_date = datetime.now(BAKU_TZ)
                sessions = parse_sessions_from_events(sorted_events, report_date=report_date)
                print(f"  Сессий найдено: {len(sessions)}")
                
                if sessions:
                    print(f"  Первая сессия: {sessions[0][0]} -> {sessions[0][1]}")
                    duration = (sessions[0][1] - sessions[0][0]).total_seconds() / 3600
                    print(f"  Длительность первой сессии: {duration:.2f} часов")
                
                # Получаем смену пользователя
                user_shift = await get_user_shift_for_date(db, user_id, report_date)
                if user_shift:
                    print(f"  Смена: {user_shift.name}")
                    shift_time_range = get_shift_time_range(user_shift, report_date)
                    if shift_time_range:
                        print(f"  Время смены: {shift_time_range[0]} -> {shift_time_range[1]}")
                        
                        # Рассчитываем часы
                        hours_in, hours_out = calculate_hours_for_sessions(
                            sessions, shift_time_range[0], shift_time_range[1], user_id=user_id
                        )
                        print(f"  ✓ Часы в смене: {hours_in:.2f}")
                        print(f"  ✓ Часы вне смены: {hours_out:.2f}")
                        print(f"  ✓ Всего отработано: {hours_in + hours_out:.2f} часов")
                    else:
                        print(f"  ⚠ Нет расписания смены для этого дня")
                else:
                    print(f"  ⚠ Пользователь не привязан к смене")
                    # Рассчитываем без смены
                    hours_in, hours_out = calculate_hours_for_sessions(
                        sessions, None, None, user_id=user_id
                    )
                    print(f"  ✓ Часы вне смены: {hours_out:.2f}")
            
            # Тестируем endpoint /reports/daily
            print(f"\n--- Тестирование endpoint /reports/daily ---")
            from datetime import date
            test_date = date.today() - timedelta(days=1)  # Вчера
            
            # Получаем события за вчера
            start_datetime = datetime.combine(test_date, time.min, tzinfo=BAKU_TZ)
            end_datetime = datetime.combine(test_date, time.max, tzinfo=BAKU_TZ)
            
            events_yesterday = await crud.get_all_events_for_day(db, start_datetime, end_datetime)
            print(f"  Событий за {test_date}: {len(events_yesterday)}")
            
            if events_yesterday:
                # Группируем по пользователям
                user_events_yesterday = {}
                for event in events_yesterday:
                    if event.user_id:
                        if event.user_id not in user_events_yesterday:
                            user_events_yesterday[event.user_id] = []
                        user_events_yesterday[event.user_id].append(event)
                
                print(f"  Пользователей с событиями: {len(user_events_yesterday)}")
                
                # Тестируем расчет для одного пользователя
                if user_events_yesterday:
                    test_user_id = list(user_events_yesterday.keys())[0]
                    test_events = sorted(user_events_yesterday[test_user_id], key=lambda x: x.timestamp)
                    
                    report_datetime = datetime.combine(test_date, time.min, tzinfo=BAKU_TZ)
                    test_sessions = parse_sessions_from_events(test_events, report_date=report_datetime)
                    
                    test_user_shift = await get_user_shift_for_date(db, test_user_id, report_datetime)
                    if test_user_shift:
                        test_shift_range = get_shift_time_range(test_user_shift, report_datetime)
                        if test_shift_range:
                            test_hours_in, test_hours_out = calculate_hours_for_sessions(
                                test_sessions, test_shift_range[0], test_shift_range[1], user_id=test_user_id
                            )
                            print(f"  ✓ Тестовый расчет для пользователя {test_user_id}:")
                            print(f"    Сессий: {len(test_sessions)}")
                            print(f"    Часы в смене: {test_hours_in:.2f}")
                            print(f"    Часы вне смены: {test_hours_out:.2f}")
            
            print(f"\n{'=' * 60}")
            print("✓ Тестирование с реальными данными завершено успешно!")
            print(f"{'=' * 60}")
            
        except Exception as e:
            print(f"\n✗ Ошибка при тестировании: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_real_data())

