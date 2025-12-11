import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';

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

  // Получение устройств
  const { data: devices } = useQuery({
    queryKey: ['devices'],
    queryFn: async () => {
      const res = await axios.get('/api/devices/');
      return res.data;
    },
    staleTime: Infinity,
    gcTime: 24 * 60 * 60 * 1000,
  });

  // Получение событий с терминала
  const { data: eventsData, isLoading, refetch } = useQuery({
    queryKey: ['device-events', selectedDeviceId, startDate, endDate],
    queryFn: async () => {
      if (!selectedDeviceId) return null;
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      params.append('max_records', '500');
      
      const res = await axios.get(`/api/devices/${selectedDeviceId}/events?${params.toString()}`);
      return res.data;
    },
    enabled: !!selectedDeviceId,
    retry: false,
    staleTime: 0, // Всегда получаем свежие данные с терминала
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
      alert(`Синхронизация завершена!\nСинхронизировано: ${data.data.stats.synced}\nПропущено: ${data.data.stats.skipped}`);
    },
    onError: (error) => {
      alert('Ошибка синхронизации: ' + (error.response?.data?.detail || error.message));
    }
  });

  const handleSync = () => {
    if (window.confirm('Синхронизировать события с терминала в базу данных?')) {
      syncMutation.mutate();
    }
  };

  const formatDateTime = (dateString) => {
    if (!dateString) return 'N/A';
    try {
      const date = new Date(dateString);
      return date.toLocaleString('ru-RU', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      });
    } catch {
      return dateString;
    }
  };

  const getEventTypeLabel = (eventType) => {
    if (eventType === 'entry') {
      return <span className="px-2.5 py-1 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800 shadow-soft">Вход</span>;
    } else if (eventType === 'exit') {
      return <span className="px-2.5 py-1 inline-flex text-xs leading-5 font-semibold rounded-full bg-red-100 text-red-800 shadow-soft">Выход</span>;
    }
    return <span className="px-2.5 py-1 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800 shadow-soft">{eventType}</span>;
  };

  return (
    <div className="px-4 py-6 sm:px-0">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-semibold text-gray-900 tracking-tight">События с терминала</h1>
      </div>

      {/* Фильтры */}
      <div className="bg-white shadow-card rounded-lg p-4 mb-6 border border-gray-100">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
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
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-soft"
            >
              <option value="">Выберите устройство</option>
              {devices?.map((device) => (
                <option key={device.id} value={device.id}>
                  {device.name} ({device.ip_address})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Начальная дата</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-soft"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Конечная дата</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-soft"
            />
          </div>

          <div className="flex items-end gap-2">
            <button
              onClick={() => refetch()}
              disabled={!selectedDeviceId || isLoading}
              className="flex-1 bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 shadow-medium transition-shadow duration-200 font-medium disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {isLoading ? 'Загрузка...' : 'Обновить'}
            </button>
            <button
              onClick={handleSync}
              disabled={!selectedDeviceId || syncMutation.isPending}
              className="flex-1 bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 shadow-medium transition-shadow duration-200 font-medium disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {syncMutation.isPending ? 'Синхронизация...' : 'Синхронизировать'}
            </button>
          </div>
        </div>
      </div>

      {/* Список событий */}
      {selectedDeviceId ? (
        isLoading ? (
          <div className="bg-white shadow-card rounded-lg p-8 text-center border border-gray-100">
            <div className="text-gray-500">Загрузка событий с терминала...</div>
          </div>
        ) : eventsData ? (
          <div className="bg-white shadow-card rounded-lg overflow-hidden border border-gray-100">
            <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
              <div className="flex justify-between items-center">
                <h2 className="text-lg font-semibold text-gray-900 tracking-tight">
                  События ({eventsData.count || 0})
                </h2>
                {eventsData.period && (
                  <div className="text-sm text-gray-500">
                    Период: {new Date(eventsData.period.start_date).toLocaleDateString('ru-RU')} - {new Date(eventsData.period.end_date).toLocaleDateString('ru-RU')}
                  </div>
                )}
              </div>
            </div>

            {eventsData.events && eventsData.events.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Время
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        ID сотрудника
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Тип события
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Терминал
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {eventsData.events.map((event, index) => (
                      <tr key={index} className="hover:bg-gray-50 transition-colors duration-150">
                        <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                          {formatDateTime(event.timestamp)}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700 font-medium">
                          {event.employee_no || 'N/A'}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm">
                          {getEventTypeLabel(event.event_type)}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                          {event.terminal_ip || 'N/A'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="px-4 py-8 text-center text-gray-500">
                События не найдены за выбранный период
              </div>
            )}
          </div>
        ) : (
          <div className="bg-white shadow-card rounded-lg p-8 text-center border border-gray-100">
            <div className="text-red-500">Ошибка загрузки событий с терминала</div>
          </div>
        )
      ) : (
        <div className="bg-white shadow-card rounded-lg p-8 text-center border border-gray-100">
          <div className="text-gray-400">Выберите устройство для просмотра событий</div>
        </div>
      )}
    </div>
  );
};

export default EventsPage;


