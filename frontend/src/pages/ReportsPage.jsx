import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { format } from 'date-fns';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Skeleton from '../components/ui/Skeleton';
import Input from '../components/ui/Input';
import EmptyState from '../components/ui/EmptyState';
import Button from '../components/ui/Button';
import Dropdown, { DropdownItem } from '../components/ui/Dropdown';
import { ChartBarIcon, ArrowDownTrayIcon, ChevronDownIcon, WifiIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline';
import { exportToPDF, exportToExcel } from '../utils/export';
import { useReportsWebSocket } from '../hooks/useWebSocket';

const ReportsPage = () => {
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);

  const { data: report, isLoading, refetch } = useQuery({
    queryKey: ['report', date],
    queryFn: async () => {
      const res = await axios.get(`/api/reports/daily?date_str=${date}`);
      return res.data;
    }
  });

  // WebSocket для обновлений отчетов в реальном времени
  const { isConnected, lastMessage } = useReportsWebSocket({
    enabled: true,
    onMessage: (message) => {
      if (message.type === 'report_update') {
        // Обновляем отчет при получении обновления
        refetch();
      }
    }
  });

  // Обновляем отчет при получении новых событий (если дата - сегодня)
  useEffect(() => {
    if (lastMessage?.type === 'event_update') {
      const today = new Date().toISOString().split('T')[0];
      if (date === today) {
        // Небольшая задержка для обработки события в БД
        setTimeout(() => refetch(), 1000);
      }
    }
  }, [lastMessage, date, refetch]);

  return (
    <div role="main">
      <header className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900" id="reports-page-title">
            Дневной отчет
          </h1>
          <p className="mt-1 text-sm text-gray-500" id="reports-page-description">
            Отчет о посещаемости сотрудников за выбранный день
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
          {report && report.length > 0 && (
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
              <DropdownItem onClick={() => exportToPDF(report, 'Дневной отчет посещаемости', 'daily-report')}>
                Экспорт в PDF
              </DropdownItem>
              <DropdownItem onClick={() => exportToExcel(report, 'daily-report')}>
                Экспорт в Excel
              </DropdownItem>
            </Dropdown>
          )}
        </div>
      </header>

      {/* Статистические карточки */}
      {report && report.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-6 mb-6">
          <Card>
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-900">{report.length}</div>
              <div className="text-sm text-gray-500">Всего сотрудников</div>
            </div>
          </Card>
          <Card>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {report.filter(r => r.status === 'Present').length}
              </div>
              <div className="text-sm text-gray-500">Присутствовали</div>
            </div>
          </Card>
          <Card>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600">
                {report.filter(r => r.status === 'Absent').length}
              </div>
              <div className="text-sm text-gray-500">Прогул</div>
            </div>
          </Card>
          <Card>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {report.reduce((sum, r) => sum + r.hours_in_shift, 0).toFixed(1)} ч.
              </div>
              <div className="text-sm text-gray-500">Часы в смене</div>
            </div>
          </Card>
          <Card>
            <div className="text-center">
              <div className="text-2xl font-bold text-orange-600">
                {report.reduce((sum, r) => sum + r.hours_outside_shift, 0).toFixed(1)} ч.
              </div>
              <div className="text-sm text-gray-500">Часы вне смены</div>
            </div>
          </Card>
          <Card>
            <div className="text-center">
              <div className="text-2xl font-bold text-[rgb(19,91,147)]">
                {report.reduce((sum, r) => sum + r.hours_worked, 0).toFixed(1)} ч.
              </div>
              <div className="text-sm text-gray-500">Всего часов</div>
            </div>
          </Card>
        </div>
      )}

      {isLoading ? (
        <Card>
          <div className="space-y-4">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="flex items-center gap-4">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-6 w-20" />
              </div>
            ))}
          </div>
        </Card>
      ) : report && report.length > 0 ? (
        <Card>
          {/* Desktop table view */}
          <div className="hidden lg:block overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Сотрудник
                    </th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Вход
                    </th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Выход
                    </th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Часы в смене
                    </th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Часы вне смены
                    </th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Всего часов
                    </th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Статус
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {report?.map((row, idx) => (
                    <tr key={idx}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {row.user}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {row.entry_time ? new Date(row.entry_time).toLocaleTimeString('ru-RU', { 
                          hour: '2-digit', 
                          minute: '2-digit',
                          timeZone: 'Asia/Baku'
                        }) : '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {row.exit_time ? new Date(row.exit_time).toLocaleTimeString('ru-RU', { 
                          hour: '2-digit', 
                          minute: '2-digit',
                          timeZone: 'Asia/Baku'
                        }) : '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-green-600 font-medium">
                        {row.hours_in_shift} ч.
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-orange-600 font-medium">
                        {row.hours_outside_shift} ч.
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-bold">
                        {row.hours_worked} ч.
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <Badge
                          variant={
                            row.status === 'Present' ? 'success' :
                            row.status === 'Absent' ? 'error' :
                            row.status === 'Present (no exit)' ? 'warning' :
                            'warning'
                          }
                        >
                          {row.status === 'Present' ? 'Присутствовал' :
                           row.status === 'Absent' ? 'Прогул' :
                           row.status === 'Present (no exit)' ? 'Присутствовал (без выхода)' :
                           'Ошибка данных'}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

          {/* Mobile card view */}
          <div className="lg:hidden space-y-3">
            {report?.map((row, idx) => (
              <div key={idx} className="bg-white border border-gray-200 rounded-lg p-4 shadow-soft hover:shadow-medium transition-shadow duration-150">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold text-gray-900">{row.user}</p>
                    <Badge
                      variant={
                        row.status === 'Present' ? 'success' :
                        row.status === 'Absent' ? 'error' :
                        row.status === 'Present (no exit)' ? 'warning' :
                        'warning'
                      }
                    >
                      {row.status === 'Present' ? 'Присутствовал' :
                       row.status === 'Absent' ? 'Прогул' :
                       row.status === 'Present (no exit)' ? 'Присутствовал (без выхода)' :
                       'Ошибка данных'}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-gray-500">Вход:</span>
                      <span className="ml-1 text-gray-700 font-medium">
                        {row.entry_time ? new Date(row.entry_time).toLocaleTimeString('ru-RU', { 
                          hour: '2-digit', 
                          minute: '2-digit',
                          timeZone: 'Asia/Baku'
                        }) : '-'}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-500">Выход:</span>
                      <span className="ml-1 text-gray-700 font-medium">
                        {row.exit_time ? new Date(row.exit_time).toLocaleTimeString('ru-RU', { 
                          hour: '2-digit', 
                          minute: '2-digit',
                          timeZone: 'Asia/Baku'
                        }) : '-'}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-500">В смене:</span>
                      <span className="ml-1 text-green-600 font-medium">{row.hours_in_shift} ч.</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Вне смены:</span>
                      <span className="ml-1 text-orange-600 font-medium">{row.hours_outside_shift} ч.</span>
                    </div>
                    <div className="col-span-2">
                      <span className="text-gray-500">Всего часов:</span>
                      <span className="ml-1 text-gray-900 font-bold">{row.hours_worked} ч.</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
        ) : (
          <Card>
            <EmptyState
              icon={ChartBarIcon}
              title="Нет данных"
              description="За выбранный день нет данных о посещаемости"
            />
          </Card>
        )}
    </div>
  );
};

export default ReportsPage;

