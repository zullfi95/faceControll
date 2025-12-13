"""
Телеграм бот для отправки ежедневных отчетов по посещаемости.

Функциональность:
- Отправка ежедневных отчетов с часами работы
- Уведомления о незакрытых сессиях
- Форматирование сообщений для удобного чтения
"""
import logging
import aiohttp
from typing import List, Dict, Optional
from datetime import datetime, date

logger = logging.getLogger(__name__)


class TelegramBot:
    """Класс для работы с Telegram Bot API."""

    def __init__(self, token: str, chat_id: str):
        """
        Инициализация бота.

        Args:
            token: Токен телеграм бота
            chat_id: ID чата для отправки сообщений
        """
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"

    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """
        Отправка сообщения в телеграм.

        Args:
            text: Текст сообщения
            parse_mode: Режим форматирования (HTML, Markdown, etc.)

        Returns:
            True если сообщение отправлено успешно
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/sendMessage"
                data = {
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True
                }

                async with session.post(url, data=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("ok"):
                            logger.info("Message sent successfully to Telegram")
                            return True
                        else:
                            logger.error(f"Telegram API error: {result}")
                    else:
                        logger.error(f"HTTP error {response.status}: {await response.text()}")

        except Exception as e:
            logger.error(f"Error sending message to Telegram: {e}", exc_info=True)

        return False


class DailyReportFormatter:
    """Форматирование ежедневных отчетов для Telegram."""

    @staticmethod
    def format_daily_report(report_date: date, employees: List[Dict],
                          unclosed_sessions: List[Dict]) -> str:
        """
        Форматирование полного ежедневного отчета.

        Args:
            report_date: Дата отчета
            employees: Список сотрудников с данными о работе
            unclosed_sessions: Список незакрытых сессий

        Returns:
            Отформатированный текст отчета
        """
        lines = []

        # Заголовок
        lines.append("📊 <b>ЕЖЕДНЕВНЫЙ ОТЧЕТ ПОСЕЩАЕМОСТИ</b>")
        lines.append(f"📅 Дата: {report_date.strftime('%d.%m.%Y')}")

        # Статистика
        total_employees = len(employees)
        present_count = sum(1 for emp in employees if emp['status'] == 'Present')
        absent_count = sum(1 for emp in employees if emp['status'] == 'Absent')

        total_shift_hours = sum(emp['hours_in_shift'] for emp in employees)
        total_outside_hours = sum(emp['hours_outside_shift'] for emp in employees)

        lines.append("📈 <b>СТАТИСТИКА:</b>")
        lines.append(f"👥 Всего сотрудников: {total_employees}")
        lines.append(f"✅ Присутствовали: {present_count}")
        lines.append(f"❌ Прогул: {absent_count}")
        lines.append(f"⏰ В смене: {total_shift_hours:.1f} ч.")
        lines.append(f"🏠 Вне смены: {total_outside_hours:.1f} ч.")
        # Детальный отчет по сотрудникам
        if employees:
            lines.append("👷 <b>СОТРУДНИКИ:</b>")
            for emp in employees:
                status_emoji = "✅" if emp['status'] == 'Present' else "❌"
                lines.append(f"{status_emoji} <b>{emp['user']}</b>")
                lines.append(f"   🏢 В смене: {emp['hours_in_shift']:.1f} ч.")
                lines.append(f"   🏠 Вне смены: {emp['hours_outside_shift']:.1f} ч.")
                lines.append(f"   📊 Итого: {emp['hours_worked']:.1f} ч.")
                if emp.get('entry_time'):
                    lines.append(f"   🕐 Вход: {emp['entry_time'][:5] if emp['entry_time'] else '-'}")
                if emp.get('exit_time'):
                    lines.append(f"   🕐 Выход: {emp['exit_time'][:5] if emp['exit_time'] else '-'}")
                lines.append("")  # Пустая строка между сотрудниками

        # Незакрытые сессии
        if unclosed_sessions:
            lines.append("⚠️ <b>НЕЗАКРЫТЫЕ СЕССИИ:</b>")
            for session in unclosed_sessions:
                lines.append(f"🚨 <b>{session['user']}</b>")
                lines.append(f"   🕐 Вошел: {session['entry_time'][:5]}")
                lines.append(f"   ⏱️ Прошло: {session['hours_since_entry']:.1f} ч.")
                lines.append("")

        # Подвал
        lines.append("🤖 Отчет сгенерирован автоматически")

        return "\n".join(lines)

    @staticmethod
    def format_unclosed_sessions_alert(unclosed_sessions: List[Dict]) -> str:
        """
        Форматирование уведомления о незакрытых сессиях.

        Args:
            unclosed_sessions: Список незакрытых сессий

        Returns:
            Отформатированный текст уведомления
        """
        if not unclosed_sessions:
            return ""

        lines = []
        lines.append("🚨 <b>ВНИМАНИЕ! НЕЗАКРЫТЫЕ СЕССИИ</b>")
        lines.append("")

        for session in unclosed_sessions:
            lines.append(f"👤 <b>{session['user']}</b>")
            lines.append(f"   🕐 Время входа: {session['entry_time'][:5]}")
            lines.append(f"   ⏱️ Прошло времени: {session['hours_since_entry']:.1f} ч.")
            lines.append("")

        lines.append("💡 Рекомендуется проверить терминалы!")

        return "\n".join(lines)
