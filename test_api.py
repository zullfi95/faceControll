#!/usr/bin/env python3
import asyncio
import httpx
import json

async def test_api():
    async with httpx.AsyncClient(base_url='http://localhost:8000') as client:
        # Получаем данные отчетов
        response = await client.get('/reports/daily?date_str=2025-12-25')
        if response.status_code == 200:
            data = response.json()
            print('✅ API работает')
            print(f'Количество смен: {len(data.get("shifts", []))}')

            if data.get('shifts'):
                shift = data['shifts'][0]
                print(f'Смена: {shift["shift_name"]}')
                print(f'Количество дней: {len(shift.get("days", []))}')

                if shift.get('days'):
                    day = shift['days'][0]
                    print(f'День: {day["day_name"]}')
                    print(f'Количество сотрудников: {len(day.get("employees", []))}')

                    if day.get('employees'):
                        emp = day['employees'][0]
                        print(f'Пример сотрудника: {emp["user_name"]} - {emp["status"]}')
                        print('Доступные статусы в данных:')
                        statuses = set()
                        event_types = set()
                        shifts = set()
                        days = set()

                        # Собираем уникальные значения для фильтров
                        for s in data.get('shifts', []):
                            shifts.add(s['shift_name'])
                            for d in s.get('days', []):
                                days.add(d['day_name'])
                                for e in d.get('employees', []):
                                    statuses.add(e['status'])
                                    if e.get('last_event_type'):
                                        event_types.add(e['last_event_type'])

                        print(f'Смены: {sorted(shifts)}')
                        print(f'Дни: {sorted(days)}')
                        print(f'Статусы: {sorted(statuses)}')
                        print(f'Типы событий: {sorted(event_types)}')
        else:
            print(f'❌ Ошибка API: {response.status_code}')
            print(response.text)

if __name__ == '__main__':
    asyncio.run(test_api())
