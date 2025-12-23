import React, { useState, useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { format, parseISO } from 'date-fns';
import { ru } from 'date-fns/locale';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Skeleton from '../components/ui/Skeleton';
import Input from '../components/ui/Input';
import EmptyState from '../components/ui/EmptyState';
import Button from '../components/ui/Button';
import Dropdown, { DropdownItem } from '../components/ui/Dropdown';
import { ChartBarIcon, ArrowDownTrayIcon, ChevronDownIcon, WifiIcon, ExclamationTriangleIcon, ChevronRightIcon, XMarkIcon } from '@heroicons/react/24/outline';
import { exportToPDF, exportToExcel } from '../utils/export';
import { useReportsWebSocket } from '../hooks/useWebSocket';

const DAY_NAMES = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'];
const DAY_SHORT_NAMES = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

const ReportsPage = () => {
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [selectedShift, setSelectedShift] = useState(null);
  const [selectedDay, setSelectedDay] = useState(null);

  const { data: reportData, isLoading, refetch, error: reportError } = useQuery({
    queryKey: ['report', date],
    queryFn: async () => {
      try {
        const res = await axios.get(`/api/reports/daily?date_str=${date}`);
        return res.data;
      } catch (error) {
        throw new Error(error.response?.data?.detail || error.message || 'Failed to load report');
      }
    },
    // Автоматическое обновление каждые 30 секунд для сегодняшней даты
    refetchInterval: (query) => {
      const today = new Date().toISOString().split('T')[0];
      return date === today ? 30000 : false; // Обновляем только для сегодня
    },
    refetchIntervalInBackground: true, // Обновлять даже когда вкладка не активна
  });

  // WebSocket для обновлений отчетов в реальном времени
  const wsOptions = useMemo(() => ({
    enabled: true,
    onMessage: (message) => {
      if (message.type === 'report_update') {
        refetch();
      }
    }
  }), [refetch]);

  const { isConnected, lastMessage } = useReportsWebSocket(wsOptions);

  // Обновляем отчет при получении новых событий (если дата - сегодня)
  useEffect(() => {
    if (lastMessage?.type === 'event_update') {
      const today = new Date().toISOString().split('T')[0];
      if (date === today) {
        setTimeout(() => refetch(), 1000);
      }
    }
  }, [lastMessage, date, refetch]);

  const handleDayClick = (shift, day) => {
    if (selectedShift?.shift_id === shift.shift_id && selectedDay?.day_of_week === day.day_of_week) {
      // Закрываем если уже открыто
      setSelectedShift(null);
      setSelectedDay(null);
    } else {
      setSelectedShift(shift);
      setSelectedDay(day);
    }
  };

  const closeModal = () => {
    setSelectedShift(null);
    setSelectedDay(null);
  };

  const formatTime = (timeStr) => {
    if (!timeStr) return 'Не зафиксирован';
    try {
      return format(parseISO(timeStr), 'dd.MM.yyyy HH:mm', { locale: ru });
    } catch (e) {
      return timeStr;
    }
  };

  const formatHoursToTime = (hours) => {
    if (hours === null || hours === undefined || isNaN(hours)) {
      return '00:00';
    }
    const totalMinutes = Math.round(hours * 60);
    const h = Math.floor(totalMinutes / 60);
    const m = totalMinutes % 60;
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
  };

  const formatEventType = (type) => {
    if (!type) return '';
    return type === 'entry' ? 'вход' : 'выход';
  };

  const getStatusBadge = (status) => {
    const variants = {
      'Present': { variant: 'success', label: 'Присутствует' },
      'Absent': { variant: 'error', label: 'Отсутствует' },
      'Present (no exit)': { variant: 'success', label: 'Присутствует (нет выхода)' }
    };
    const config = variants[status] || { variant: 'default', label: status };
    return <Badge variant={config.variant}>{config.label}</Badge>;
  };

  // Преобразуем данные для экспорта
  const getExportData = () => {
    if (!reportData?.shifts) return [];
    const exportData = [];
    reportData.shifts.forEach(shift => {
      shift.days.forEach(day => {
        day.employees.forEach(emp => {
          exportData.push({
            user: emp.user_name,
            hikvision_id: emp.hikvision_id,
            shift_start_time: emp.shift_start_time || null,
            shift_duration_hours: emp.shift_duration_hours || (day.schedule ? (() => {
              // Вычисляем продолжительность смены из расписания
              try {
                const [startHour, startMin] = (day.schedule.start || '09:00').split(':').map(Number);
                const [endHour, endMin] = (day.schedule.end || '18:00').split(':').map(Number);
                const start = startHour * 60 + startMin;
                let end = endHour * 60 + endMin;
                if (end < start) end += 24 * 60; // Смена через полночь
                return (end - start) / 60;
              } catch {
                return null;
              }
            })() : null),
            entry_time: emp.first_entry_time || null,
            delay_minutes: emp.delay_minutes || null,
            last_authentication: emp.last_entry_exit_time || null,
            entry_exit_type: emp.last_event_type || null,
            hours_worked_total: emp.hours_worked_total || (emp.hours_in_shift + emp.hours_outside_shift),
            hours_in_shift: emp.hours_in_shift,
            hours_outside_shift: emp.hours_outside_shift,
            status: emp.status
          });
        });
      });
    });
    return exportData;
  };

  if (isLoading) {
    return (
      <div role="main">
        <div className="mb-6">
          <Skeleton className="h-8 w-64 mb-2" />
          <Skeleton className="h-4 w-96" />
        </div>
        <Card>
          <Skeleton className="h-64 w-full" />
        </Card>
      </div>
    );
  }

  if (reportError) {
    return (
      <div role="main">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Отчеты по посещаемости</h1>
        </div>
        <Card>
          <div className="p-6 text-center">
            <p className="text-red-600 mb-4">Ошибка загрузки отчета: {reportError.message}</p>
            <Button onClick={() => refetch()}>Попробовать снова</Button>
          </div>
        </Card>
      </div>
    );
  }

  const shifts = reportData?.shifts || [];

  return (
    <div role="main">
      <header className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900" id="reports-page-title">
            Отчет по посещаемости по сменам
          </h1>
          <p className="mt-1 text-sm text-gray-500" id="reports-page-description">
            Детальная информация о посещаемости сотрудников, сгруппированная по сменам
          </p>
        </div>
        <div className="flex items-center gap-4 w-full sm:w-auto">
          <div className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${
            isConnected
              ? 'bg-green-100 text-green-800'
              : 'bg-red-100 text-red-800'
          }`}>
            {isConnected ? (
              <WifiIcon className="w-3 h-3" />
            ) : (
              <ExclamationTriangleIcon className="w-3 h-3" />
            )}
            {isConnected ? 'Онлайн' : 'Оффлайн'}
          </div>
          <Input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            aria-label="Выберите дату отчета"
          />
          {shifts.length > 0 && (
            <Dropdown
              trigger={
                <Button variant="outline" aria-label="Экспорт отчета">
                  <ArrowDownTrayIcon className="h-4 w-4 mr-2" aria-hidden="true" />
                  Экспорт
                  <ChevronDownIcon className="h-4 w-4 ml-2" aria-hidden="true" />
                </Button>
              }
              aria-label="Опции экспорта"
            >
              <DropdownItem onClick={() => exportToPDF(getExportData(), 'Отчет по сменам', 'shift-report')}>
                Экспорт в PDF
              </DropdownItem>
              <DropdownItem onClick={() => exportToExcel(getExportData(), 'shift-report')}>
                Экспорт в Excel
              </DropdownItem>
            </Dropdown>
          )}
        </div>
      </header>

      {shifts.length === 0 ? (
        <EmptyState
          icon={ChartBarIcon}
          title="Нет данных"
          description="На выбранную дату нет активных смен или сотрудников"
        />
      ) : (
        <div className="space-y-6">
          {shifts.map((shift) => (
            <Card key={shift.shift_id} className="p-6">
              <div className="mb-4">
                <h2 className="text-xl font-semibold text-gray-900">{shift.shift_name}</h2>
                {shift.shift_description && (
                  <p className="text-sm text-gray-500 mt-1">{shift.shift_description}</p>
                )}
              </div>

              <div className="grid grid-cols-7 gap-2">
                {shift.days.map((day) => (
                  <button
                    key={day.day_of_week}
                    onClick={() => handleDayClick(shift, day)}
                    className={`
                      p-3 rounded-lg border-2 transition-all
                      ${day.is_active
                        ? 'border-blue-500 bg-blue-50 text-blue-700 font-semibold'
                        : 'border-gray-200 bg-gray-50 text-gray-600 hover:border-gray-300'
                      }
                      ${selectedShift?.shift_id === shift.shift_id && selectedDay?.day_of_week === day.day_of_week
                        ? 'ring-2 ring-blue-300'
                        : ''
                      }
                    `}
                    aria-label={`${day.day_name}, сотрудников: ${day.employees.length}`}
                  >
                    <div className="text-xs font-medium mb-1">{DAY_SHORT_NAMES[day.day_of_week]}</div>
                    <div className="text-lg font-bold">{day.employees.length}</div>
                    <div className="text-xs mt-1">сотрудников</div>
                  </button>
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Модальное окно с деталями дня */}
      {selectedShift && selectedDay && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" onClick={closeModal}>
          <div className="bg-white rounded-lg shadow-xl max-w-[95vw] w-full max-h-[90vh] overflow-hidden flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between p-6 border-b">
              <div>
                <h3 className="text-xl font-semibold text-gray-900">
                  {selectedShift.shift_name} - {selectedDay.day_name}
                </h3>
                {selectedDay.schedule && (
                  <p className="text-sm text-gray-500 mt-1">
                    Время смены: {selectedDay.schedule.start} - {selectedDay.schedule.end}
                  </p>
                )}
              </div>
              <button
                onClick={closeModal}
                className="text-gray-400 hover:text-gray-600"
                aria-label="Закрыть"
              >
                <XMarkIcon className="h-6 w-6" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6">
              {selectedDay.employees.length === 0 ? (
                <EmptyState
                  title="Нет сотрудников"
                  description="В этот день нет сотрудников, привязанных к смене"
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                          Сотрудник
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                          Время начала смены
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                          Первый вход (время)
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                          Опоздание
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                          Последняя аутентификация
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                          Часов в смене
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                          Время за смену
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                          Время вне смены
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                          Зашел/Вышел
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                          Статус
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {selectedDay.employees.map((emp) => (
                        <tr key={emp.user_id} className="hover:bg-gray-50">
                          <td className="px-4 py-4 whitespace-nowrap">
                            <div className="font-medium text-gray-900">{emp.user_name}</div>
                            <div className="text-sm text-gray-500">{emp.hikvision_id}</div>
                          </td>
                          <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                            {emp.shift_start_time || '—'}
                          </td>
                          <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                            {formatTime(emp.first_entry_time)}
                          </td>
                          <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                            {emp.delay_minutes !== null && emp.delay_minutes !== undefined 
                              ? `${emp.delay_minutes} мин`
                              : '—'}
                          </td>
                          <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                            {formatTime(emp.last_entry_exit_time)}
                          </td>
                          <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                            {emp.shift_duration_hours !== null && emp.shift_duration_hours !== undefined
                              ? formatHoursToTime(emp.shift_duration_hours)
                              : '—'}
                          </td>
                          <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                            {formatHoursToTime(emp.hours_in_shift)}
                          </td>
                          <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                            {formatHoursToTime(emp.hours_outside_shift)}
                          </td>
                          <td className="px-4 py-4 whitespace-nowrap">
                            {emp.last_event_type ? (
                              <Badge variant={emp.last_event_type === 'entry' ? 'success' : 'warning'}>
                                {formatEventType(emp.last_event_type)}
                              </Badge>
                            ) : (
                              <span className="text-gray-400">—</span>
                            )}
                          </td>
                          <td className="px-4 py-4 whitespace-nowrap">
                            {getStatusBadge(emp.status)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReportsPage;
