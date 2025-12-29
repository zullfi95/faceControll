import React, { useState, useMemo, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { motion } from 'framer-motion';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import Skeleton from '../components/ui/Skeleton';
import EmptyState from '../components/ui/EmptyState';
import Badge from '../components/ui/Badge';
import Dropdown, { DropdownItem } from '../components/ui/Dropdown';
import VirtualizedTable from '../components/ui/VirtualizedTable';
import showToast from '../utils/toast';
import { CalendarIcon, ArrowDownTrayIcon, ChevronDownIcon, WifiIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline';
import { exportToPDF, exportToExcel } from '../utils/export';
import { useEventsWebSocket } from '../hooks/useWebSocket';

const EventsPage = () => {
  const queryClient = useQueryClient();
  const [selectedDeviceId, setSelectedDeviceId] = useState(() => {
    const saved = localStorage.getItem('selectedDeviceId');
    return saved ? parseInt(saved) : null;
  });
  const [startDate, setStartDate] = useState(() => {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    return yesterday.toISOString().split('T')[0];
  });
  const [endDate, setEndDate] = useState(() => {
    return new Date().toISOString().split('T')[0];
  });
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(24);

  // WebSocket для реального времени обновлений
  // Включаем WebSocket для получения уведомлений о новых событиях
  const wsOptions = useMemo(() => ({
    enabled: true, // Включаем WebSocket для получения уведомлений
    maxReconnectAttempts: 3, // Ограничиваем попытки переподключения
    reconnectInterval: 10000, // Интервал между попытками
    onMessage: (message) => {
      if (message.type === 'event_update') {
        const eventData = message.data;

        // Показываем уведомление
        if (eventData && eventData.employee_no) {
          const eventType = eventData.event_type === 'entry' ? 'Вход' : eventData.event_type === 'exit' ? 'Выход' : 'Событие';
          showToast(`${eventType}: ${eventData.name || eventData.employee_no}`, 'info');
        } else {
          showToast('Новое событие получено!', 'info');
        }

        // Принудительно обновляем список событий
        queryClient.invalidateQueries(['device-events']);
        queryClient.invalidateQueries(['events']);
      }
    },
    onError: () => {
      // Тихая обработка ошибок - не логируем каждую ошибку
    }
  }), [selectedDeviceId, queryClient]);

  const { isConnected, lastMessage } = useEventsWebSocket(wsOptions);
  const [showOnlyEmployees, setShowOnlyEmployees] = useState(true); // Фильтр: показывать только события сотрудников

  // Получение устройств
  const { data: devices } = useQuery({
    queryKey: ['devices'],
    queryFn: async () => {
      const res = await axios.get('/api/devices/');
      return res.data;
    },
    staleTime: 5 * 60 * 1000, // 5 минут - данные считаются свежими
    gcTime: 24 * 60 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000, // Обновляем каждые 5 минут
  });


  // Получение событий с терминала
  const { data: eventsData, isLoading, refetch } = useQuery({
    queryKey: ['device-events', selectedDeviceId, startDate, endDate],
    queryFn: async () => {
      if (!selectedDeviceId) return null;
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      params.append('max_records', '1000');
      
      const res = await axios.get(`/api/devices/${selectedDeviceId}/events?${params.toString()}`);
      return res.data;
    },
    enabled: !!selectedDeviceId,
    retry: false,
    staleTime: 0, // Данные всегда считаются устаревшими, чтобы обновляться при invalidateQueries
    refetchOnWindowFocus: true, // Обновляем при фокусе окна
    refetchOnMount: true, // Обновляем при монтировании
    // Автоматическое обновление каждые 30 секунд для актуальных данных
    refetchInterval: 30000,
    refetchIntervalInBackground: true,
  });

  // Синхронизация событий в БД
  const syncMutation = useMutation({
    mutationFn: async () => {
      if (!selectedDeviceId) return;
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      
      return axios.post(`/api/devices/${selectedDeviceId}/sync-events?${params.toString()}`);
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries(['device-events']);
      showToast.success(`Синхронизация завершена! Синхронизировано: ${data.data.stats.synced}, Пропущено: ${data.data.stats.skipped}`);
    },
    onError: (error) => {
      showToast.error('Ошибка синхронизации: ' + (error.response?.data?.detail || error.message));
    }
  });

  // Настройка webhook
  const configureWebhookMutation = useMutation({
    mutationFn: async () => {
      if (!selectedDeviceId) return;
      return axios.post(`/api/devices/${selectedDeviceId}/webhook/configure`);
    },
    onSuccess: (data) => {
      if (data.data.success) {
        showToast.success('Webhook успешно настроен');
      } else {
        showToast.warning('Webhook настроен, но может потребоваться ручная настройка: ' + (data.data.message || ''));
      }
    },
    onError: (error) => {
      showToast.error('Ошибка настройки webhook: ' + (error.response?.data?.detail || error.message));
    }
  });


  const [syncConfirm, setSyncConfirm] = useState(false);

  const handleSync = () => {
    setSyncConfirm(true);
  };

  const formatDateTime = (dateString) => {
    if (!dateString) return '--';
    try {
      const date = new Date(dateString);
      // Конвертируем в часовой пояс Баку (UTC+4, Asia/Baku)
      return date.toLocaleString('ru-RU', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        timeZone: 'Asia/Baku'
      });
    } catch {
      return dateString;
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return '--';
    try {
      const date = new Date(dateString);
      // Конвертируем в часовой пояс Баку (UTC+4, Asia/Baku)
      return date.toLocaleDateString('ru-RU', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        timeZone: 'Asia/Baku'
      });
    } catch {
      return dateString;
    }
  };

  // Фильтруем события: показываем только события сотрудников, если включен фильтр
  const events = eventsData?.events || [];
  const filteredEvents = React.useMemo(() => {
    if (showOnlyEmployees) {
      return events.filter(event => event.employee_no && event.employee_no.trim() !== '');
    }
    return events;
  }, [events, showOnlyEmployees]);

  // Пагинация
  const totalEvents = filteredEvents.length;
  const totalPages = Math.ceil(totalEvents / pageSize);
  const startIndex = (currentPage - 1) * pageSize;
  const endIndex = startIndex + pageSize;
  const paginatedEvents = filteredEvents.slice(startIndex, endIndex);

  // Сброс страницы при изменении фильтров
  React.useEffect(() => {
    setCurrentPage(1);
  }, [startDate, endDate, selectedDeviceId, pageSize, showOnlyEmployees]);

  return (
    <div role="main">
      <header className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900 tracking-tight" id="events-page-title">
              События с терминала
            </h1>
            <p className="mt-1 text-sm text-gray-500" id="events-page-description">
              Просмотр и управление событиями доступа с терминалов
            </p>
          </div>
          <div className="flex items-center gap-2">
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
          </div>
        </div>
      </header>

      {/* Фильтры */}
      <Card className="mb-6">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Устройство</label>
            <select
              value={selectedDeviceId || ''}
              onChange={(e) => {
                const id = e.target.value ? parseInt(e.target.value) : null;
                setSelectedDeviceId(id);
                if (id) {
                  localStorage.setItem('selectedDeviceId', id.toString());
                } else {
                  localStorage.removeItem('selectedDeviceId');
                }
              }}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[rgb(19,91,147)] shadow-soft"
            >
              <option value="">Все терминалы</option>
              {devices?.map((device) => {
                const icon = device.device_type === 'entry' ? '🚪' :
                             device.device_type === 'exit' ? '🚶' :
                             device.device_type === 'both' ? '🔄' : '📍';
                return (
                  <option key={device.id} value={device.id}>
                    {icon} {device.name} - {device.location || device.ip_address}
                  </option>
                );
              })}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Начальная дата</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[rgb(19,91,147)] shadow-soft"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Конечная дата</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[rgb(19,91,147)] shadow-soft"
            />
          </div>

          <div className="flex items-end">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={showOnlyEmployees}
                onChange={(e) => {
                  setShowOnlyEmployees(e.target.checked);
                  setCurrentPage(1);
                }}
                className="w-4 h-4 text-[rgb(19,91,147)] border-gray-300 rounded focus:ring-[rgb(19,91,147)]"
              />
              <span className="text-sm font-medium text-gray-700">
                Только события сотрудников
              </span>
            </label>
          </div>

          <div className="flex flex-col gap-2 items-start">
            <Button
              onClick={() => refetch()}
              disabled={!selectedDeviceId || isLoading}
              loading={isLoading}
            >
              Обновить
            </Button>
            <Button
              variant="success"
              onClick={handleSync}
              disabled={!selectedDeviceId || syncMutation.isPending}
              loading={syncMutation.isPending}
            >
              Синхронизировать
            </Button>
            {filteredEvents && filteredEvents.length > 0 && (
              <Dropdown
                trigger={
                  <Button variant="outline" aria-label="Экспорт событий">
                    <ArrowDownTrayIcon className="h-4 w-4 mr-2" aria-hidden="true" />
                    Экспорт
                    <ChevronDownIcon className="h-4 w-4 ml-2" aria-hidden="true" />
                  </Button>
                }
                aria-label="Опции экспорта событий"
              >
                <DropdownItem onClick={() => exportToPDF(eventsData.events, 'Terminal Events Report', 'events')}>
                  Экспорт в PDF
                </DropdownItem>
                <DropdownItem onClick={() => exportToExcel(eventsData.events, 'events')}>
                  Экспорт в Excel
                </DropdownItem>
              </Dropdown>
            )}
          </div>

        </div>
      </Card>

      {/* Список событий */}
      {selectedDeviceId ? (
        isLoading ? (
          <Card>
            <div className="space-y-4">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="flex items-center gap-4">
                  <Skeleton className="h-4 w-12" />
                  <Skeleton className="h-4 flex-1" />
                  <Skeleton className="h-4 w-24" />
                </div>
              ))}
            </div>
          </Card>
        ) : eventsData ? (
          <Card
            title="События"
            subtitle={eventsData.period ? `Период: ${formatDate(eventsData.period.start_date)} - ${formatDate(eventsData.period.end_date)}` : undefined}
          >

            {filteredEvents && filteredEvents.length > 0 ? (
              <>
                {/* Desktop table view */}
                <div className="hidden lg:block">
                {filteredEvents.length > 100 ? (
                  <VirtualizedTable
                    columns={[
                      {
                        key: 'no',
                        label: 'No.',
                        width: '5%',
                        render: (_, event, index) => startIndex + index + 1,
                      },
                      {
                        key: 'employee_no',
                        label: 'Employee ID',
                        width: '10%',
                        sortable: true,
                      },
                      {
                        key: 'name',
                        label: 'Name',
                        width: '15%',
                        sortable: true,
                      },
                      {
                        key: 'device_name',
                        label: 'Terminal',
                        width: '12%',
                        render: (_, event) => {
                          // Ищем устройство, чтобы получить его тип
                          const device = devices?.find(d => d.name === event.device_name);
                          const deviceType = device?.device_type || 'other';
                          
                          const bgColor = deviceType === 'entry' ? 'bg-green-50' :
                                         deviceType === 'exit' ? 'bg-orange-50' :
                                         deviceType === 'both' ? 'bg-blue-50' :
                                         'bg-gray-50';
                          const textColor = deviceType === 'entry' ? 'text-green-700' :
                                           deviceType === 'exit' ? 'text-orange-700' :
                                           deviceType === 'both' ? 'text-blue-700' :
                                           'text-gray-700';
                          const icon = deviceType === 'entry' ? '🚪' :
                                      deviceType === 'exit' ? '🚶' :
                                      deviceType === 'both' ? '🔄' : '📍';
                          
                          return (
                            <span className={`text-xs px-2 py-1 rounded ${bgColor} ${textColor}`}>
                              {icon} {event.device_name || 'N/A'}
                            </span>
                          );
                        },
                      },
                      {
                        key: 'card_no',
                        label: 'Card No.',
                        width: '8%',
                      },
                      {
                        key: 'card_reader_id',
                        label: 'Card Reader ID',
                        width: '10%',
                      },
                      {
                        key: 'event_type',
                        label: 'Event Types',
                        width: '12%',
                        render: (_, event) => (
                          <Badge variant={event.event_type === 'entry' ? 'success' : event.event_type === 'exit' ? 'warning' : 'primary'}>
                            {event.event_type_description || event.event_type || '--'}
                          </Badge>
                        ),
                      },
                      {
                        key: 'timestamp',
                        label: 'Time',
                        width: '18%',
                        sortable: true,
                        render: (_, event) => formatDateTime(event.timestamp),
                      },
                      {
                        key: 'remote_host_ip',
                        label: 'Remote Host IP',
                        width: '10%',
                      },
                      {
                        key: 'operation',
                        label: 'Operation',
                        width: '10%',
                        render: () => '--',
                      },
                    ]}
                    data={paginatedEvents}
                    height={600}
                    itemSize={60}
                    aria-label="Список событий"
                  />
                ) : (
                  <div className="overflow-x-auto">
                  <table 
                    className="min-w-full divide-y divide-gray-200"
                    role="table"
                    aria-label="Список событий терминала"
                  >
                    <caption className="sr-only">Таблица событий доступа с терминалов</caption>
                    <thead className="bg-gray-50">
                      <tr role="row">
                        <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" role="columnheader">
                          No.
                        </th>
                        <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" role="columnheader">
                          Employee ID
                        </th>
                        <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" role="columnheader">
                          Name
                        </th>
                        <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" role="columnheader">
                          Terminal
                        </th>
                        <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" role="columnheader">
                          Card No.
                        </th>
                        <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" role="columnheader">
                          Card Reader ID
                        </th>
                        <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" role="columnheader">
                          Event Types
                        </th>
                        <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" role="columnheader">
                          Time
                        </th>
                        <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" role="columnheader">
                          Remote Host IP
                        </th>
                        <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" role="columnheader">
                          Operation
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200" role="rowgroup">
                      {paginatedEvents.map((event, index) => (
                        <tr key={index} className="hover:bg-gray-50 transition-colors duration-150" role="row">
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                            {startIndex + index + 1}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">
                            {event.employee_no || '--'}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">
                            {event.name || '--'}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm">
                            {(() => {
                              const device = devices?.find(d => d.name === event.device_name);
                              const deviceType = device?.device_type || 'other';
                              
                              const bgColor = deviceType === 'entry' ? 'bg-green-50' :
                                             deviceType === 'exit' ? 'bg-orange-50' :
                                             deviceType === 'both' ? 'bg-blue-50' :
                                             'bg-gray-50';
                              const textColor = deviceType === 'entry' ? 'text-green-700' :
                                               deviceType === 'exit' ? 'text-orange-700' :
                                               deviceType === 'both' ? 'text-blue-700' :
                                               'text-gray-700';
                              const icon = deviceType === 'entry' ? '🚪' :
                                          deviceType === 'exit' ? '🚶' :
                                          deviceType === 'both' ? '🔄' : '📍';
                              
                              return (
                                <span className={`text-xs px-2 py-1 rounded ${bgColor} ${textColor}`}>
                                  {icon} {event.device_name || 'N/A'}
                                </span>
                              );
                            })()}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">
                            {event.card_no || '--'}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">
                            {event.card_reader_id || '--'}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">
                            {event.event_type_description || event.event_type || '--'}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">
                            {formatDateTime(event.timestamp)}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">
                            {event.remote_host_ip || '--'}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                            {/* Иконки для операций можно добавить здесь */}
                            --
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                )}
                </div>

                {/* Mobile card view */}
                <div className="lg:hidden space-y-3">
                  {paginatedEvents.map((event, index) => (
                    <motion.div
                      key={index}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.2, delay: index * 0.03 }}
                      className="bg-white border border-gray-200 rounded-lg p-4 shadow-soft hover:shadow-medium transition-shadow duration-150"
                    >
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-medium text-gray-500">#{startIndex + index + 1}</span>
                          <Badge variant={event.event_type === 'entry' ? 'success' : event.event_type === 'exit' ? 'warning' : 'primary'}>
                            {event.event_type_description || event.event_type || '--'}
                          </Badge>
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-gray-900">{event.name || '--'}</p>
                          <p className="text-xs text-gray-500 mt-0.5">ID: {event.employee_no || '--'}</p>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div>
                            <span className="text-gray-500">Карта:</span>
                            <span className="ml-1 text-gray-700 font-medium">{event.card_no || '--'}</span>
                          </div>
                          <div>
                            <span className="text-gray-500">Считыватель:</span>
                            <span className="ml-1 text-gray-700 font-medium">{event.card_reader_id || '--'}</span>
                          </div>
                          <div className="col-span-2">
                            <span className="text-gray-500">Время:</span>
                            <span className="ml-1 text-gray-700 font-medium">{formatDateTime(event.timestamp)}</span>
                          </div>
                          {event.remote_host_ip && (
                            <div className="col-span-2">
                              <span className="text-gray-500">IP:</span>
                              <span className="ml-1 text-gray-700 font-medium">{event.remote_host_ip}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </div>

                {/* Пагинация */}
                <div className="px-4 py-3 bg-gray-50 border-t border-gray-200 flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <span className="text-sm text-gray-700">
                      Total: {totalEvents}
                    </span>
                    <select
                      value={pageSize}
                      onChange={(e) => {
                        setPageSize(parseInt(e.target.value));
                        setCurrentPage(1);
                      }}
                      className="border border-gray-300 rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-[rgb(19,91,147)]"
                    >
                      <option value={24}>24</option>
                      <option value={50}>50</option>
                      <option value={100}>100</option>
                    </select>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                      disabled={currentPage === 1}
                      className="px-3 py-1 border border-gray-300 rounded-md text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100"
                    >
                      &lt;
                    </button>
                    {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                      let pageNum;
                      if (totalPages <= 5) {
                        pageNum = i + 1;
                      } else if (currentPage <= 3) {
                        pageNum = i + 1;
                      } else if (currentPage >= totalPages - 2) {
                        pageNum = totalPages - 4 + i;
                      } else {
                        pageNum = currentPage - 2 + i;
                      }
                      return (
                        <button
                          key={pageNum}
                          onClick={() => setCurrentPage(pageNum)}
                          className={`px-3 py-1 border rounded-md text-sm ${
                            currentPage === pageNum
                              ? 'bg-[rgb(19,91,147)] text-white border-[rgb(19,91,147)]'
                              : 'border-gray-300 hover:bg-gray-100'
                          }`}
                        >
                          {pageNum}
                        </button>
                      );
                    })}
                    <button
                      onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                      disabled={currentPage === totalPages}
                      className="px-3 py-1 border border-gray-300 rounded-md text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100"
                    >
                      &gt;
                    </button>
                    <div className="flex items-center gap-2 ml-4">
                      <input
                        type="number"
                        min="1"
                        max={totalPages}
                        value={currentPage}
                        onChange={(e) => {
                          const page = parseInt(e.target.value);
                          if (page >= 1 && page <= totalPages) {
                            setCurrentPage(page);
                          }
                        }}
                        className="w-16 px-2 py-1 border border-gray-300 rounded-md text-sm text-center focus:outline-none focus:ring-2 focus:ring-[rgb(19,91,147)]"
                      />
                      <span className="text-sm text-gray-700">/ {totalPages}</span>
                      <button
                        onClick={() => {
                          const page = parseInt(prompt(`Перейти на страницу (1-${totalPages}):`, currentPage) || currentPage);
                          if (page >= 1 && page <= totalPages) {
                            setCurrentPage(page);
                          }
                        }}
                        className="px-3 py-1 bg-[rgb(19,91,147)] text-white rounded-md text-sm hover:bg-[rgb(30,120,180)]"
                      >
                        Go
                      </button>
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <EmptyState
                icon={CalendarIcon}
                title="События не найдены"
                description="За выбранный период событий не найдено"
              />
            )}
          </Card>
        ) : (
          <Card>
            <div className="text-red-500 text-center py-8">Ошибка загрузки событий с терминала</div>
          </Card>
        )
      ) : (
        <Card>
          <EmptyState
            icon={CalendarIcon}
            title="Выберите устройство"
            description="Выберите устройство для просмотра событий"
          />
        </Card>
      )}

      {/* Confirm dialogs */}
      <ConfirmDialog
        isOpen={syncConfirm}
        onClose={() => setSyncConfirm(false)}
        onConfirm={() => {
          syncMutation.mutate();
          setSyncConfirm(false);
        }}
        title="Синхронизация событий"
        message="Синхронизировать события с терминала в базу данных?"
        confirmText="Синхронизировать"
        cancelText="Отмена"
        variant="info"
      />

    </div>
  );
};

export default EventsPage;
