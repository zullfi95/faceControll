import React, { useState, useMemo, useEffect, useRef } from 'react';
// Force reload comment - update time: Dec 22 2025
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { motion } from 'framer-motion';
import FacePhotoUpload from '../components/FacePhotoUpload';
import Button from '../components/ui/Button';
import Modal from '../components/ui/Modal';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import Badge from '../components/ui/Badge';
import Skeleton from '../components/ui/Skeleton';
import EmptyState from '../components/ui/EmptyState';
import Input from '../components/ui/Input';
import Card from '../components/ui/Card';
import VirtualizedTable from '../components/ui/VirtualizedTable';
import LiveRegion from '../components/accessibility/LiveRegion';
import showToast from '../utils/toast';
import { UserGroupIcon, PlusIcon } from '@heroicons/react/24/outline';
import { useEventsWebSocket } from '../hooks/useWebSocket';

const UsersPage = () => {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newUser, setNewUser] = useState({ hikvision_id: '', full_name: '', department: '' });
  const [newUserPhoto, setNewUserPhoto] = useState(null);
  const [capturedPhotoUrl, setCapturedPhotoUrl] = useState(null);
  const [selectedPhoto, setSelectedPhoto] = useState(null);
  const [editingUser, setEditingUser] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [creationStep, setCreationStep] = useState('');
  const [statisticsUser, setStatisticsUser] = useState(null);
  const [userStatistics, setUserStatistics] = useState(null);
  const [isLoadingStatistics, setIsLoadingStatistics] = useState(false);
  
  // Face capture from terminal states
  const [isCapturingFromTerminal, setIsCapturingFromTerminal] = useState(false);
  const [captureStatus, setCaptureStatus] = useState(null); // 'waiting' | 'capturing' | 'success' | 'error'
  const [captureMessage, setCaptureMessage] = useState('');

  // Получение пользователей из БД
  // Accessibility: Live region для объявлений
  const [liveMessage, setLiveMessage] = useState('');
  
  // Состояния для подтверждений (должны быть объявлены до всех хуков)
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [syncConfirm, setSyncConfirm] = useState(null);
  
  // Ref для отслеживания пользователей, которые уже синхронизируются
  const syncingUsersRef = useRef(new Set());
  
  // Сохраняем выбранное устройство в localStorage (должно быть до useQuery)
  const [selectedDeviceId, setSelectedDeviceId] = useState(() => {
    const saved = localStorage.getItem('selectedDeviceId');
    return saved ? parseInt(saved) : null;
  });
  
  const { data: users, isLoading, refetch: refetchUsers } = useQuery({
    queryKey: ['users'],
    queryFn: async () => {
      const res = await axios.get('/api/users/');
      return res.data;
    },
    staleTime: 0, // Данные всегда считаются устаревшими, чтобы получать актуальные фото
    gcTime: 24 * 60 * 60 * 1000, // 24 часа в кеше
    // Автоматическое обновление каждые 30 секунд
    refetchInterval: 30000,
    refetchIntervalInBackground: true,
  });

  // WebSocket для обновлений в реальном времени
  const wsOptions = useMemo(() => ({
    enabled: true,
    onMessage: (message) => {
      if (message.type === 'event_update') {
        // При новом событии обновляем список пользователей
        // (может быть добавлен новый пользователь или обновлен существующий)
        setTimeout(() => {
          refetchUsers();
        }, 1000);
      }
    }
  }), [refetchUsers]);

  const { isConnected: wsConnected, lastMessage } = useEventsWebSocket(wsOptions);

  // Получение устройств
  const { data: devices } = useQuery({
    queryKey: ['devices'],
    queryFn: async () => {
      const res = await axios.get('/api/devices/');
      return res.data;
    },
    staleTime: 5 * 60 * 1000, // 5 минут - данные считаются свежими
    gcTime: 24 * 60 * 60 * 1000, // 24 часа в кеше
    refetchInterval: 5 * 60 * 1000, // Обновляем каждые 5 минут
  });

  // Получение пользователей с терминала
  // Сохраняем выбранное устройство при изменении
  const handleDeviceChange = (deviceId) => {
    const id = deviceId ? parseInt(deviceId) : null;
    setSelectedDeviceId(id);
    if (id) {
      localStorage.setItem('selectedDeviceId', id.toString());
    } else {
      localStorage.removeItem('selectedDeviceId');
    }
  };

  const { data: terminalUsers, isLoading: isLoadingTerminal, refetch: refetchTerminal } = useQuery({
    queryKey: ['terminal-users', selectedDeviceId],
    queryFn: async () => {
      if (!selectedDeviceId) return null;
      const res = await axios.get(`/api/devices/${selectedDeviceId}/terminal-users`);
      return res.data;
    },
    enabled: !!selectedDeviceId,
    retry: false,
    staleTime: Infinity, // Данные никогда не считаются устаревшими
    gcTime: 24 * 60 * 60 * 1000, // 24 часа в кеше
  });


  // Запуск режима захвата лица на терминале
  const handleStartFaceCapture = async () => {
    if (!newUser.hikvision_id) {
      showToast.warning('Сначала введите ID сотрудника!');
      return;
    }
    
    setIsCapturingFromTerminal(true);
    setCaptureStatus('waiting');
    setCaptureMessage('Запуск режима захвата на терминале...');
    
    try {
      // Получаем device_id (берем первый активный)
      const devicesRes = await axios.get('/api/devices/');
      const device = devicesRes.data.find(d => d.is_active) || devicesRes.data[0];
      
      if (!device) {
        throw new Error('Устройство не найдено');
      }
      
      // Запускаем режим захвата (передаем имя для создания пользователя если нужно)
      const response = await axios.post(`/api/devices/${device.id}/start-face-capture`, {
        employee_no: newUser.hikvision_id,
        full_name: newUser.full_name || ""
      });

      if (response.data.success) {
        // Фото успешно захвачено
        setCaptureStatus('success');
        setCaptureMessage(`✅ Фото успешно захвачено! Метод: ${response.data.method}`);

        // Показываем захваченное фото
        if (response.data.photo_path) {
          // Получаем фото через API
          const photoResponse = await axios.get(`/api${response.data.photo_path}`, {
            responseType: 'blob'
          });

          const photoUrl = URL.createObjectURL(photoResponse.data);
          setCapturedPhotoUrl(photoUrl);
          
          // Создаем файл из blob для сохранения
          const file = new File([photoResponse.data], `${newUser.hikvision_id}_face.jpg`, { type: 'image/jpeg' });
          setNewUserPhoto(file);
        } else if (response.data.can_continue_without_preview) {
          // Фото захвачено на терминале, но предпросмотр недоступен из-за ограничений прав
          setCaptureMessage('✅ Фото захвачено на терминале! (Предпросмотр недоступен из-за прав доступа, но регистрация возможна)');
          
          // Создаем фиктивный файл-заглушку чтобы активировать кнопку "Сохранить"
          const placeholderBlob = new Blob([''], { type: 'image/jpeg' });
          const placeholderFile = new File([placeholderBlob], `${newUser.hikvision_id}_terminal_captured.jpg`, { type: 'image/jpeg' });
          setNewUserPhoto(placeholderFile);
        }

        // Фото уже захвачено и загружено на терминал
        setIsCapturingFromTerminal(false);
      } else {
        throw new Error(response.data.message || 'Не удалось захватить фото');
      }
    } catch (error) {
      console.error('Ошибка при захвате фото:', error);
      setCaptureStatus('error');
      setCaptureMessage('Ошибка: ' + (error.response?.data?.detail || error.message));
      setIsCapturingFromTerminal(false);
    }
  };
  

  // Создание пользователя с автоматической синхронизацией
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!newUserPhoto) {
      showToast.warning('Пожалуйста, сделайте фото на терминале или загрузите файл');
      return;
    }

    setIsCreating(true);
    
    try {
      // Шаг 1: Создание пользователя
      setCreationStep('Создание пользователя...');
      const userResponse = await axios.post('/api/users/', newUser);
      const userId = userResponse.data.id;
      
      // Шаг 2: Загрузка фото (только если это НЕ placeholder)
      const isPlaceholder = newUserPhoto.size === 0;
      
      if (!isPlaceholder) {
        setCreationStep('Загрузка фото...');
        const formData = new FormData();
        formData.append('file', newUserPhoto);
        await axios.post(`/api/users/${userId}/upload-photo`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
      } else {
        setCreationStep('Используется фото с терминала...');
      }
      
      // Шаг 3: Синхронизация с устройством
      setCreationStep('Синхронизация с терминалом...');
      await axios.post(`/api/users/${userId}/sync-to-device`);
      
      // Небольшая задержка для обеспечения обновления данных в БД
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Успех! Принудительно обновляем кеш пользователей
      await queryClient.invalidateQueries(['users']);
      await queryClient.refetchQueries(['users']);
      setIsModalOpen(false);
      setNewUser({ hikvision_id: '', full_name: '', department: '' });
      setNewUserPhoto(null);
      setCapturedPhotoUrl(null);
      setCreationStep('');
      setCaptureStatus(null);
      setCaptureMessage('');
      showToast.success('Сотрудник успешно добавлен и синхронизирован с терминалом!');
      
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.message;
      showToast.error(`Ошибка: ${errorMsg}`);
    } finally {
      setIsCreating(false);
    }
  };

  // Загрузка фото
  const uploadPhotoMutation = useMutation({
    mutationFn: async ({ userId, file }) => {
      const formData = new FormData();
      formData.append('file', file);
      return axios.post(`/api/users/${userId}/upload-photo`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
    },
    onSuccess: async (data) => {
      showToast.success('Фото успешно загружено!');
      setEditingUser(null);
      setSelectedPhoto(null);
      
      // Полностью удаляем кеш
      queryClient.removeQueries({ queryKey: ['users'] });
      
      // Обновляем данные пользователей
      await refetchUsers();
    },
    onError: (error) => {
      showToast.error('Ошибка загрузки фото: ' + (error.response?.data?.detail || error.message));
    }
  });

  // Синхронизация с устройством
  const syncMutation = useMutation({
    mutationFn: (userId) => axios.post(`/api/users/${userId}/sync-to-device`),
    onSuccess: async () => {
      await queryClient.invalidateQueries(['users']);
      await queryClient.refetchQueries(['users']);
      showToast.success('Пользователь успешно синхронизирован с устройством!');
    },
    onError: (error) => {
      showToast.error('Ошибка синхронизации: ' + (error.response?.data?.detail || error.message));
    }
  });

  // Удаление пользователя
  const deleteMutation = useMutation({
    mutationFn: (userId) => axios.delete(`/api/users/${userId}`),
    onSuccess: async () => {
      await queryClient.invalidateQueries(['users']);
      await queryClient.refetchQueries(['users']);
      showToast.success('Пользователь успешно удален!');
    },
    onError: (error) => {
      showToast.error('Ошибка удаления: ' + (error.response?.data?.detail || error.message));
    }
  });

  const handleDelete = (userId, userName) => {
    setDeleteConfirm({ userId, userName });
  };

  const handlePhotoUpload = (userId) => {
    if (!selectedPhoto) {
      showToast.warning('Выберите фото');
      return;
    }
    uploadPhotoMutation.mutate({ userId, file: selectedPhoto });
  };

  const handleSync = (userId) => {
    setSyncConfirm(userId);
  };

  // Загрузка статистики пользователя
  const handleViewStatistics = async (user) => {
    setStatisticsUser(user);
    setIsLoadingStatistics(true);
    try {
      const res = await axios.get(`/api/users/${user.id}/statistics`);
      setUserStatistics(res.data);
    } catch (error) {
      showToast.error('Ошибка загрузки статистики: ' + (error.response?.data?.detail || error.message));
      setStatisticsUser(null);
    } finally {
      setIsLoadingStatistics(false);
    }
  };

  // Автосинхронизация пользователей с фото
  useEffect(() => {
    if (!users || users.length === 0) return;
    
    // Автоматически синхронизируем пользователей с фото, которые еще не синхронизированы
    const usersToSync = users.filter(user => 
      user.id &&
      user.photo_path && 
      !user.synced_to_device && 
      user.is_active &&
      !syncingUsersRef.current.has(user.id) // Проверяем, что пользователь еще не синхронизируется
    );
    
    if (usersToSync.length > 0) {
      // Синхронизируем по одному пользователю с небольшой задержкой
      usersToSync.forEach((user, index) => {
        // Добавляем пользователя в набор синхронизирующихся
        syncingUsersRef.current.add(user.id);
        
        setTimeout(async () => {
          try {
            await axios.post(`/api/users/${user.id}/sync-to-device`);
            await queryClient.invalidateQueries(['users']);
          } catch (error) {
            // Тихая ошибка - не показываем уведомление для автосинхронизации
          } finally {
            // Удаляем пользователя из набора после завершения (успешного или неудачного)
            syncingUsersRef.current.delete(user.id);
          }
        }, index * 1000); // Задержка 1 секунда между синхронизациями
      });
    }
    
    // Очищаем набор от пользователей, которые уже синхронизированы в БД
    users.forEach(user => {
      if (user.synced_to_device && syncingUsersRef.current.has(user.id)) {
        syncingUsersRef.current.delete(user.id);
      }
    });
  }, [users, queryClient]);

  // Объединяем пользователей из БД и терминала
  const mergedUsers = useMemo(() => {
    if (!users) return [];
    
    // Создаем Map для быстрого поиска пользователей из БД по hikvision_id
    const dbUsersMap = new Map();
    users.forEach(user => {
      dbUsersMap.set(user.hikvision_id, user);
    });
    
    // Создаем объединенный список
    const merged = [];
    const processedIds = new Set();
    
    // Сначала добавляем пользователей из БД
    users.forEach(user => {
      merged.push({
        ...user,
        source: 'db',
        terminalData: null
      });
      processedIds.add(user.hikvision_id);
    });
    
    // Затем добавляем пользователей с терминала, которых нет в БД
    if (terminalUsers && selectedDeviceId) {
      terminalUsers.forEach(terminalUser => {
        const employeeNo = terminalUser.employeeNo;
        if (employeeNo && !processedIds.has(employeeNo)) {
          merged.push({
            id: null,
            hikvision_id: employeeNo,
            full_name: terminalUser.name || 'Не указано',
            department: null,
            photo_path: null,
            is_active: true,
            synced_to_device: false,
            role: 'cleaner',
            source: 'terminal',
            terminalData: terminalUser
          });
          processedIds.add(employeeNo);
        } else if (employeeNo && processedIds.has(employeeNo)) {
          // Обновляем данные пользователя из БД информацией с терминала
          const dbUser = dbUsersMap.get(employeeNo);
          if (dbUser) {
            const index = merged.findIndex(u => u.id === dbUser.id);
            if (index !== -1) {
              merged[index] = {
                ...merged[index],
                terminalData: terminalUser
              };
            }
          }
        }
      });
    }
    
    return merged;
  }, [users, terminalUsers, selectedDeviceId]);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-10 w-40" />
        </div>
        <Card>
          <div className="space-y-4">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="flex items-center gap-4">
                <Skeleton variant="circular" width={48} height={48} />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-3 w-48" />
                </div>
                <Skeleton className="h-8 w-24" />
              </div>
            ))}
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <LiveRegion message={liveMessage} priority="polite" />
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 tracking-tight">Добавить пользователя</h1>
          <p className="mt-1 text-sm text-gray-500">
            Управление сотрудниками и их фотографиями для распознавания
          </p>
        </div>
        <div className="flex items-center gap-4 w-full sm:w-auto">
          {devices && devices.length > 0 && (
            <select
              value={selectedDeviceId || ''}
              onChange={(e) => {
                handleDeviceChange(e.target.value);
              }}
              className="flex-1 sm:flex-none border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[rgb(19,91,147)]"
            >
              <option value="">Все устройства</option>
              {devices.map((device) => (
                <option key={device.id} value={device.id}>
                  {device.name} ({device.ip_address})
                </option>
              ))}
            </select>
          )}
          <Button onClick={() => setIsModalOpen(true)} aria-describedby="users-page-description">
            <PlusIcon className="h-4 w-4 mr-2" aria-hidden="true" />
            Добавить пользователя
          </Button>
        </div>
      </div>

      {/* Объединенная таблица сотрудников */}
      {mergedUsers && mergedUsers.length === 0 ? (
        <Card>
          <EmptyState
            icon={UserGroupIcon}
            title="Нет сотрудников"
            description="Начните с добавления первого сотрудника в систему"
            action={
              <Button onClick={() => setIsModalOpen(true)}>
                <PlusIcon className="h-4 w-4 mr-2" />
                Добавить пользователя
              </Button>
            }
          />
        </Card>
      ) : (
        <>
          {/* Desktop table view */}
          <div className="hidden lg:block">
          {mergedUsers && mergedUsers.length > 50 ? (
            // Виртуализированная таблица для больших списков
            <VirtualizedTable
              columns={[
                {
                  key: 'user',
                  label: 'Сотрудник',
                  width: '40%',
                  render: (_, user) => (
                    <div>
                      <div className="text-sm font-medium text-gray-900">
                        {user.full_name || 'Без имени'}
                      </div>
                      <div className="text-sm text-gray-500">
                        ID: {user.hikvision_id}
                      </div>
                    </div>
                  ),
                },
                {
                  key: 'status',
                  label: 'Статус',
                  width: '30%',
                  render: (_, user) => (
                    <div className="flex flex-wrap gap-1">
                      <Badge variant={user.is_active ? 'success' : 'error'}>
                        {user.is_active ? 'Активен' : 'Неактивен'}
                      </Badge>
                      {user.synced_to_device && (
                        <Badge variant="primary">Синхронизирован</Badge>
                      )}
                      {user.terminalData && user.terminalData.numOfFace > 0 && (
                        <Badge variant="purple">
                          {user.terminalData.numOfFace} фото
                        </Badge>
                      )}
                    </div>
                  ),
                },
                {
                  key: 'actions',
                  label: 'Действия',
                  width: '30%',
                  render: (_, user) => (
                    user.id ? (
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditingUser(user);
                          }}
                        >
                          Фото
                        </Button>
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleViewStatistics(user);
                          }}
                        >
                          Статистика
                        </Button>
                        <Button
                          variant="success"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleSync(user.id);
                          }}
                          disabled={!user.photo_path || syncMutation.isPending}
                          loading={syncMutation.isPending}
                        >
                          Синхр.
                        </Button>
                        <Button
                          variant="error"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(user.id, user.full_name);
                          }}
                          disabled={deleteMutation.isPending}
                          loading={deleteMutation.isPending}
                        >
                          Удалить
                        </Button>
                      </div>
                    ) : null
                  ),
                },
              ]}
              data={mergedUsers}
              height={600}
              itemSize={80}
              aria-label="Список сотрудников"
            />
          ) : (
            // Обычная таблица для небольших списков
            <Card>
            <div className="overflow-x-auto">
              <table 
                className="min-w-full divide-y divide-gray-200"
                role="table"
                aria-label="Список сотрудников"
              >
                <caption className="sr-only">Таблица сотрудников с информацией о статусе и действиях</caption>
                <thead className="bg-gray-50">
                  <tr role="row">
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" role="columnheader">
                      Сотрудник
                    </th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" role="columnheader">
                      Статус
                    </th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" role="columnheader">
                      Действия
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200" role="rowgroup">
                  {mergedUsers?.map((user) => (
                    <tr key={user.id || user.hikvision_id} className="hover:bg-gray-50" role="row">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div>
                          <div className="text-sm font-medium text-gray-900">
                            {user.full_name || 'Без имени'}
                          </div>
                          <div className="text-sm text-gray-500">
                            ID: {user.hikvision_id}
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex flex-wrap gap-1">
                          <Badge variant={user.is_active ? 'success' : 'error'}>
                            {user.is_active ? 'Активен' : 'Неактивен'}
                          </Badge>
                          {user.synced_to_device && (
                            <Badge variant="primary">Синхронизирован</Badge>
                          )}
                          {user.terminalData && user.terminalData.numOfFace > 0 && (
                            <Badge variant="purple">
                              {user.terminalData.numOfFace} фото
                            </Badge>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        {user.id && (
                          <div className="flex items-center gap-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setEditingUser(user)}
                            >
                              Фото
                            </Button>
                            <Button
                              variant="primary"
                              size="sm"
                              onClick={() => handleViewStatistics(user)}
                            >
                              Статистика
                            </Button>
                        <Button
                          variant="success"
                          size="sm"
                          onClick={() => handleSync(user.id)}
                          disabled={!user.photo_path || syncMutation.isPending}
                          loading={syncMutation.isPending}
                          aria-label={`Синхронизировать ${user.full_name || user.hikvision_id} с терминалом`}
                        >
                          Синхр.
                        </Button>
                        <Button
                          variant="error"
                          size="sm"
                          onClick={() => handleDelete(user.id, user.full_name)}
                          disabled={deleteMutation.isPending}
                          loading={deleteMutation.isPending}
                          aria-label={`Удалить сотрудника ${user.full_name || user.hikvision_id}`}
                        >
                          Удалить
                        </Button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
          )}
          </div>

          {/* Mobile card view */}
          <div className="lg:hidden">
          <Card>
            <div className="divide-y divide-gray-200">
              {mergedUsers?.map((user, index) => (
                <motion.div
                  key={user.id || user.hikvision_id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2, delay: index * 0.03 }}
                  className="px-4 py-4 sm:px-6 hover:bg-gray-50 transition-colors duration-150"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold text-gray-900 truncate">{user.full_name}</p>
                      <p className="flex items-center text-sm text-gray-500 mt-0.5">
                        ID: <span className="font-medium text-gray-700 ml-1">{user.hikvision_id}</span> | Отдел: <span className="ml-1">{user.department || 'Не указан'}</span>
                        {user.source === 'terminal' && (
                          <span className="ml-2 px-2 py-0.5 text-xs bg-yellow-100 text-yellow-800 rounded-full">
                            Только на терминале
                          </span>
                        )}
                      </p>
                    </div>
                    <div className="ml-2 flex items-center space-x-2">
                      <Badge variant={user.is_active ? 'success' : 'error'}>
                        {user.is_active ? 'Активен' : 'Неактивен'}
                      </Badge>
                      {user.synced_to_device && (
                        <Badge variant="primary">Синхронизирован</Badge>
                      )}
                      {user.terminalData && user.terminalData.numOfFace > 0 && (
                        <Badge variant="purple">
                          {user.terminalData.numOfFace} фото на терминале
                        </Badge>
                      )}
                      {user.id && (
                        <div className="flex items-center gap-2 flex-wrap">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setEditingUser(user)}
                          >
                            Фото
                          </Button>
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={() => handleViewStatistics(user)}
                          >
                            Статистика
                          </Button>
                          <Button
                            variant="success"
                            size="sm"
                            onClick={() => handleSync(user.id)}
                            disabled={!user.photo_path || syncMutation.isPending}
                            loading={syncMutation.isPending}
                          >
                            Синхронизировать
                          </Button>
                          <Button
                            variant="error"
                            size="sm"
                            onClick={() => handleDelete(user.id, user.full_name)}
                            disabled={deleteMutation.isPending}
                            loading={deleteMutation.isPending}
                          >
                            Удалить
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </Card>
        </div>
        </>
      )}


      {/* Модалка редактирования фото */}
      <Modal
        isOpen={!!editingUser}
        onClose={() => {
          setEditingUser(null);
          setSelectedPhoto(null);
        }}
        title={`Загрузка фото для ${editingUser?.full_name}`}
        footer={
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              onClick={() => {
                setEditingUser(null);
                setSelectedPhoto(null);
              }}
            >
              Отмена
            </Button>
            <Button
              onClick={() => handlePhotoUpload(editingUser.id)}
              disabled={!selectedPhoto || uploadPhotoMutation.isPending}
              loading={uploadPhotoMutation.isPending}
            >
              Сохранить
            </Button>
          </div>
        }
      >
        {editingUser && (
          <FacePhotoUpload
            onPhotoSelect={setSelectedPhoto}
            currentPhoto={editingUser.photo_path ? `/api${editingUser.photo_path.startsWith('/') ? editingUser.photo_path : '/' + editingUser.photo_path}` : null}
          />
        )}
      </Modal>

      {/* Модалка добавления пользователя */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setNewUser({ hikvision_id: '', full_name: '', department: '' });
          setNewUserPhoto(null);
          setCapturedPhotoUrl(null);
          setCaptureStatus(null);
          setCaptureMessage('');
          setIsCapturingFromTerminal(false);
        }}
        title="Добавить пользователя"
        size="xl"
        footer={
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              onClick={() => {
                setIsModalOpen(false);
                setNewUser({ hikvision_id: '', full_name: '', department: '' });
                setNewUserPhoto(null);
                setCapturedPhotoUrl(null);
                setCaptureStatus(null);
                setCaptureMessage('');
                setIsCapturingFromTerminal(false);
              }}
              disabled={isCreating}
            >
              Отмена
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={isCreating || !newUserPhoto}
              loading={isCreating}
            >
              Сохранить и синхронизировать
            </Button>
          </div>
        }
      >
        <form onSubmit={handleSubmit}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Левая колонка - данные */}
            <div className="space-y-4">
              <Input
                label="ID (с терминала)"
                type="text"
                required
                disabled={isCreating}
                value={newUser.hikvision_id}
                onChange={(e) => setNewUser({...newUser, hikvision_id: e.target.value})}
                placeholder="Например: 1001"
              />
              <Input
                label="ФИО"
                type="text"
                required
                disabled={isCreating}
                value={newUser.full_name}
                onChange={(e) => setNewUser({...newUser, full_name: e.target.value})}
              />
              <Input
                label="Отдел"
                type="text"
                disabled={isCreating}
                value={newUser.department}
                onChange={(e) => setNewUser({...newUser, department: e.target.value})}
              />
            </div>
                
            {/* Правая колонка - фото */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Фото для распознавания лица
              </label>
              
              {/* Кнопка захвата с терминала */}
              <div className="mb-3">
                <Button
                  type="button"
                  variant="success"
                  onClick={handleStartFaceCapture}
                  disabled={isCapturingFromTerminal || isCreating || !newUser.hikvision_id}
                  loading={isCapturingFromTerminal}
                  className="w-full"
                >
                  Захват с терминала
                </Button>
                    
                    {/* Статус захвата */}
                    {captureStatus && (
                      <div className={`mt-2 p-3 rounded-md text-sm ${
                        captureStatus === 'success' ? 'bg-green-50 border border-green-200 text-green-800' :
                        captureStatus === 'error' ? 'bg-red-50 border border-red-200 text-red-800' :
                        'bg-blue-50 border border-blue-200 text-blue-800'
                      }`}>
                        {captureMessage}
                        {captureStatus === 'capturing' && (
                          <div className="mt-2 text-xs text-blue-600">
                            ⏳ Ожидание захвата лица на терминале...
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                  
                  {/* Загрузка файла */}
                  <FacePhotoUpload
                    onPhotoSelect={setNewUserPhoto}
                    currentPhoto={capturedPhotoUrl ? (capturedPhotoUrl.startsWith('blob:') ? capturedPhotoUrl : `/api${capturedPhotoUrl}`) : null}
                  />
                </div>

            {/* Прогресс создания */}
            {isCreating && (
              <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-md">
                <div className="flex items-center">
                  <svg className="animate-spin h-5 w-5 text-blue-600 mr-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span className="text-sm text-blue-800">{creationStep}</span>
                </div>
              </div>
            )}
          </div>
        </form>
      </Modal>

      {/* Confirm dialogs */}
      <ConfirmDialog
        isOpen={!!deleteConfirm}
        onClose={() => setDeleteConfirm(null)}
        onConfirm={() => {
          if (deleteConfirm) {
            deleteMutation.mutate(deleteConfirm.userId);
          }
        }}
        title="Удаление сотрудника"
        message={`Вы уверены, что хотите удалить сотрудника "${deleteConfirm?.userName}"? Это действие нельзя отменить.`}
        confirmText="Удалить"
        cancelText="Отмена"
        variant="error"
      />

      <ConfirmDialog
        isOpen={!!syncConfirm}
        onClose={() => setSyncConfirm(null)}
        onConfirm={() => {
          if (syncConfirm) {
            syncMutation.mutate(syncConfirm);
          }
        }}
        title="Синхронизация"
        message="Синхронизировать пользователя с терминалом?"
        confirmText="Синхронизировать"
        cancelText="Отмена"
        variant="info"
      />

      {/* Модалка статистики пользователя */}
      <Modal
        isOpen={!!statisticsUser}
        onClose={() => {
          setStatisticsUser(null);
          setUserStatistics(null);
        }}
        title={`Статистика: ${statisticsUser?.full_name || statisticsUser?.hikvision_id || 'Пользователь'}`}
      >
        {isLoadingStatistics ? (
          <div className="flex justify-center items-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : userStatistics ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <Card className="p-4">
                <div className="text-sm text-gray-500 mb-1">Всего событий</div>
                <div className="text-2xl font-bold text-gray-900">{userStatistics.total_events}</div>
              </Card>
              <Card className="p-4">
                <div className="text-sm text-gray-500 mb-1">Входов</div>
                <div className="text-2xl font-bold text-green-600">{userStatistics.total_entry_events}</div>
              </Card>
              <Card className="p-4">
                <div className="text-sm text-gray-500 mb-1">Выходов</div>
                <div className="text-2xl font-bold text-orange-600">{userStatistics.total_exit_events}</div>
              </Card>
              <Card className="p-4">
                <div className="text-sm text-gray-500 mb-1">Сегодня</div>
                <div className="text-2xl font-bold text-blue-600">{userStatistics.events_today}</div>
              </Card>
              <Card className="p-4">
                <div className="text-sm text-gray-500 mb-1">За 7 дней</div>
                <div className="text-2xl font-bold text-purple-600">{userStatistics.events_last_7_days}</div>
              </Card>
              <Card className="p-4">
                <div className="text-sm text-gray-500 mb-1">За 30 дней</div>
                <div className="text-2xl font-bold text-indigo-600">{userStatistics.events_last_30_days}</div>
              </Card>
            </div>
            {userStatistics.first_event_date && (
              <div className="text-sm text-gray-600">
                <div>Первое событие: {new Date(userStatistics.first_event_date).toLocaleString('ru-RU')}</div>
                {userStatistics.last_event_date && (
                  <div>Последнее событие: {new Date(userStatistics.last_event_date).toLocaleString('ru-RU')}</div>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">Нет данных</div>
        )}
      </Modal>
    </div>
  );
};

export default UsersPage;

