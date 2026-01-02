"""
Unit тесты для логики расчета часов работы.
"""

import pytest
from datetime import datetime, time, timedelta, timezone
from typing import List, Dict
import sys
import os

# Добавляем путь к приложению
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.utils.hours_calculation import (
    calculate_work_hours_in_shift,
    calculate_work_hours_outside_shift,
    get_shift_schedule_for_day,
    split_session_by_shift,
    BAKU_TZ
)


class TestHoursCalculation:
    """Тесты для функций расчета часов."""

    def test_calculate_work_hours_in_shift_basic(self):
        """Тест базового расчета часов в смене."""
        # Смена с 9:00 до 18:00
        shift_start = time(9, 0)
        shift_end = time(18, 0)
        shift_duration_hours = 9.0

        # Сессия полностью в смене: 10:00 - 17:00 (7 часов)
        session_start = datetime(2024, 1, 1, 10, 0, tzinfo=BAKU_TZ)
        session_end = datetime(2024, 1, 1, 17, 0, tzinfo=BAKU_TZ)

        hours_in_shift = calculate_work_hours_in_shift(
            session_start, session_end, shift_start, shift_end, shift_duration_hours
        )

        assert hours_in_shift == 7.0

    def test_calculate_work_hours_in_shift_partial(self):
        """Тест расчета часов в смене для частичной сессии."""
        # Смена с 9:00 до 18:00
        shift_start = time(9, 0)
        shift_end = time(18, 0)
        shift_duration_hours = 9.0

        # Сессия частично в смене: 8:00 - 12:00 (4 часа в смене из 9)
        session_start = datetime(2024, 1, 1, 8, 0, tzinfo=BAKU_TZ)
        session_end = datetime(2024, 1, 1, 12, 0, tzinfo=BAKU_TZ)

        hours_in_shift = calculate_work_hours_in_shift(
            session_start, session_end, shift_start, shift_end, shift_duration_hours
        )

        assert hours_in_shift == 3.0  # 12:00 - 9:00 = 3 часа

    def test_calculate_work_hours_outside_shift(self):
        """Тест расчета часов вне смены."""
        # Смена с 9:00 до 18:00
        shift_start = time(9, 0)
        shift_end = time(18, 0)

        # Сессия частично вне смены: 8:00 - 12:00 (1 час вне смены)
        session_start = datetime(2024, 1, 1, 8, 0, tzinfo=BAKU_TZ)
        session_end = datetime(2024, 1, 1, 12, 0, tzinfo=BAKU_TZ)

        hours_outside = calculate_work_hours_outside_shift(
            session_start, session_end, shift_start, shift_end
        )

        assert hours_outside == 1.0  # 9:00 - 8:00 = 1 час

    def test_split_session_by_shift(self):
        """Тест разделения сессии на части внутри и вне смены."""
        # Смена с 9:00 до 18:00
        shift_start = time(9, 0)
        shift_end = time(18, 0)

        # Сессия пересекает смену: 8:00 - 20:00
        session_start = datetime(2024, 1, 1, 8, 0, tzinfo=BAKU_TZ)
        session_end = datetime(2024, 1, 1, 20, 0, tzinfo=BAKU_TZ)

        in_shift, outside_shift = split_session_by_shift(
            session_start, session_end, shift_start, shift_end
        )

        assert in_shift == 9.0  # 18:00 - 9:00 = 9 часов
        assert outside_shift == 3.0  # (9:00 - 8:00) + (20:00 - 18:00) = 3 часа

    def test_shift_schedule_for_day(self):
        """Тест получения расписания смены для дня недели."""
        # Смена с расписанием по дням
        shift_schedule = {
            "0": {"start": "09:00", "end": "18:00", "enabled": True},  # Понедельник
            "1": {"start": "10:00", "end": "19:00", "enabled": True},  # Вторник
        }

        # Понедельник (weekday 0)
        schedule = get_shift_schedule_for_day(shift_schedule, 0)
        assert schedule["start"] == "09:00"
        assert schedule["end"] == "18:00"
        assert schedule["enabled"] is True

        # Вторник (weekday 1)
        schedule = get_shift_schedule_for_day(shift_schedule, 1)
        assert schedule["start"] == "10:00"
        assert schedule["end"] == "19:00"
        assert schedule["enabled"] is True

        # Суббота (weekday 5) - нет в расписании
        schedule = get_shift_schedule_for_day(shift_schedule, 5)
        assert schedule is None

    def test_shift_overnight(self):
        """Тест смены через полночь."""
        # Ночная смена: 22:00 - 06:00 следующего дня
        shift_start = time(22, 0)
        shift_end = time(6, 0)

        # Сессия в ночной смене: 23:00 - 05:00
        session_start = datetime(2024, 1, 1, 23, 0, tzinfo=BAKU_TZ)
        session_end = datetime(2024, 1, 2, 5, 0, tzinfo=BAKU_TZ)

        hours_in_shift = calculate_work_hours_in_shift(
            session_start, session_end, shift_start, shift_end, 8.0
        )

        assert hours_in_shift == 6.0  # Полностью в смене
