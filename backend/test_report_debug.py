import asyncio
import sys
sys.path.insert(0, '.')
from app.database import get_db
from app import crud, models, schemas
from datetime import datetime, time, timedelta
from app.utils.hours_calculation import BAKU_TZ, get_shift_time_range, calculate_hours_for_sessions
from app.utils.daily_report_service import parse_sessions_from_events
from sqlalchemy import select

async def full_report_test():
    async for db in get_db():
        # Параметры как в get_daily_report
        date_str = '2025-12-16'
        report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        report_datetime = datetime.combine(report_date, time.min, tzinfo=BAKU_TZ)
        weekday = report_date.weekday()

        print(f'Full report test for {report_date} (weekday {weekday})')

        # Получаем события
        start_datetime = datetime.combine(report_date, time.min, tzinfo=BAKU_TZ)
        end_datetime = datetime.combine(report_date, time.max, tzinfo=BAKU_TZ)
        extended_start_datetime = start_datetime - timedelta(days=1)

        events = await crud.get_all_events_for_day(db, extended_start_datetime, end_datetime)
        print(f'Found {len(events)} events')

        # Группируем события
        events_by_user = {}
        for event in events:
            if event.user_id:
                if event.user_id not in events_by_user:
                    events_by_user[event.user_id] = []
                events_by_user[event.user_id].append(event)

        print(f'Users with events: {list(events_by_user.keys())}')

        # Получаем смены
        shifts = await crud.get_all_work_shifts(db, active_only=True)
        print(f'Found {len(shifts)} active shifts')

        shift_reports = []

        for shift in shifts:
            print(f'\nProcessing shift {shift.id}: {shift.name}')

            # Получаем привязки
            assignments = await crud.get_user_shift_assignments(db, shift_id=shift.id, active_only=True)
            print(f'Found {len(assignments)} assignments')

            # Фильтруем по дате
            active_assignments = []
            for assignment in assignments:
                date_check = (not assignment.start_date or assignment.start_date.date() <= report_date) and \
                           (not assignment.end_date or assignment.end_date.date() >= report_date)
                if date_check:
                    active_assignments.append(assignment)

            print(f'Active assignments: {len(active_assignments)}')

            if not active_assignments:
                print('No active assignments - skipping')
                continue

            # Проверяем расписание
            day_schedule_dict = shift.schedule.get(str(weekday))
            print(f'Day schedule for weekday {weekday}: {day_schedule_dict}')

            if not day_schedule_dict or not day_schedule_dict.get('enabled', False):
                print('Schedule not enabled - skipping')
                continue

            # Создаем day_schedule
            day_schedule = schemas.DaySchedule(
                start=day_schedule_dict.get('start', '09:00'),
                end=day_schedule_dict.get('end', '18:00'),
                enabled=True
            )

            employees_for_day = []
            print(f'Processing {len(active_assignments)} assignments')

            for assignment in active_assignments:
                user = assignment.user
                user_events = sorted(events_by_user.get(user.id, []), key=lambda x: x.timestamp)
                print(f'Processing user {user.id} ({user.full_name}): {len(user_events)} events')

                # Парсим сессии
                sessions = parse_sessions_from_events(user_events, report_date=report_datetime)
                print(f'Parsed {len(sessions)} sessions')

                # Получаем время смены
                shift_time_range = get_shift_time_range(shift, report_datetime)
                print(f'Shift time range: {shift_time_range}')

                # Рассчитываем часы
                if shift_time_range:
                    hours_in_shift, hours_outside_shift = calculate_hours_for_sessions(
                        sessions, shift_time_range[0], shift_time_range[1], user_id=user.id
                    )
                else:
                    hours_in_shift, hours_outside_shift = calculate_hours_for_sessions(
                        sessions, None, None, user_id=user.id
                    )

                print(f'Hours: in_shift={hours_in_shift:.2f}, outside_shift={hours_outside_shift:.2f}')

                # Определяем статус и времена
                first_entry_time = None
                last_entry_exit_time = None
                last_event_type = None
                status = 'Absent'

                if sessions:
                    first_entry_time = sessions[0][0]
                    if len(sessions) > 0 and sessions[-1][1]:
                        last_entry_exit_time = sessions[-1][1]
                        last_event_type = 'exit'
                        status = 'Present'
                    else:
                        last_entry_exit_time = sessions[-1][0]
                        last_event_type = 'entry'
                        status = 'Present (no exit)'

                employees_for_day.append({
                    'user_id': user.id,
                    'user_name': user.full_name or f'User {user.hikvision_id}',
                    'hikvision_id': user.hikvision_id,
                    'first_entry_time': first_entry_time.isoformat() if first_entry_time else None,
                    'last_entry_exit_time': last_entry_exit_time.isoformat() if last_entry_exit_time else None,
                    'last_event_type': last_event_type,
                    'hours_in_shift': round(hours_in_shift, 2),
                    'hours_outside_shift': round(hours_outside_shift, 2),
                    'status': status
                })

            print(f'Employees for day: {len(employees_for_day)}')

            if employees_for_day:  # Только если есть сотрудники
                # Создаем day_data
                day_data = {
                    'day_of_week': weekday,
                    'day_name': ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'][weekday],
                    'is_active': True,
                    'schedule': day_schedule,
                    'employees': employees_for_day
                }

                # Добавляем shift_report
                shift_report = {
                    'shift_id': shift.id,
                    'shift_name': shift.name,
                    'shift_description': shift.description,
                    'days': [day_data],
                    'active_day': weekday
                }

                shift_reports.append(shift_report)
                print(f'Added shift report with {len(employees_for_day)} employees')

        print(f'\nFinal result: {len(shift_reports)} shifts in report')

        # Выводим детали отчета
        for shift_report in shift_reports:
            print(f'Shift: {shift_report["shift_name"]}')
            for day in shift_report['days']:
                print(f'  Day: {day["day_name"]}')
                for emp in day['employees']:
                    print(f'    Employee: {emp["user_name"]} (ID: {emp["user_id"]})')
                    print(f'      Hours in shift: {emp["hours_in_shift"]}')
                    print(f'      Hours outside shift: {emp["hours_outside_shift"]}')
                    print(f'      Status: {emp["status"]}')

        break

if __name__ == "__main__":
    asyncio.run(full_report_test())
