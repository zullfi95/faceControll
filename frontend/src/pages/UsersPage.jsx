import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import FacePhotoUpload from '../components/FacePhotoUpload';

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
  
  // Face capture from terminal states
  const [isCapturingFromTerminal, setIsCapturingFromTerminal] = useState(false);
  const [captureStatus, setCaptureStatus] = useState(null); // 'waiting' | 'capturing' | 'success' | 'error'
  const [captureMessage, setCaptureMessage] = useState('');

  // Получение пользователей из БД
  const { data: users, isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: async () => {
      const res = await axios.get('/api/users/');
      return res.data;
    },
    staleTime: Infinity, // Данные никогда не считаются устаревшими
    gcTime: 24 * 60 * 60 * 1000, // 24 часа в кеше
  });

  // Получение устройств
  const { data: devices } = useQuery({
    queryKey: ['devices'],
    queryFn: async () => {
      const res = await axios.get('/api/devices/');
      return res.data;
    },
    staleTime: Infinity, // Данные никогда не считаются устаревшими
    gcTime: 24 * 60 * 60 * 1000, // 24 часа в кеше
  });

  // Получение пользователей с терминала
  // Сохраняем выбранное устройство в localStorage
  const [selectedDeviceId, setSelectedDeviceId] = useState(() => {
    const saved = localStorage.getItem('selectedDeviceId');
    return saved ? parseInt(saved) : null;
  });

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
    console.log('🚀 [START] handleStartFaceCapture вызван');
    console.log('📋 [DATA] newUser:', newUser);
    
    if (!newUser.hikvision_id) {
      console.warn('⚠️ [VALIDATION] ID сотрудника не заполнен');
      alert('Сначала введите ID сотрудника!');
      return;
    }
    
    console.log('✅ [VALIDATION] Валидация пройдена');
    setIsCapturingFromTerminal(true);
    setCaptureStatus('waiting');
    setCaptureMessage('Запуск режима захвата на терминале...');
    
    try {
      // Получаем device_id (берем первый активный)
      console.log('🔍 [DEVICE] Получение списка устройств...');
      const devicesRes = await axios.get('/api/devices/');
      const device = devicesRes.data.find(d => d.is_active) || devicesRes.data[0];
      
      if (!device) {
        throw new Error('Устройство не найдено');
      }
      
      console.log('✅ [DEVICE] Устройство найдено:', device.id, device.name);
      
      // Запускаем режим захвата (передаем имя для создания пользователя если нужно)
      console.log('📤 [REQUEST] Отправка запроса на захват фото...');
      const response = await axios.post(`/api/devices/${device.id}/start-face-capture`, {
        employee_no: newUser.hikvision_id,
        full_name: newUser.full_name || ""
      });

      console.log('📥 [RESPONSE] Ответ получен:', {
        success: response.data.success,
        photo_path: response.data.photo_path,
        method: response.data.method
      });

      if (response.data.success) {
        // Фото успешно захвачено
        setCaptureStatus('success');
        setCaptureMessage(`✅ Фото успешно захвачено! Метод: ${response.data.method}`);

        // Показываем захваченное фото
        if (response.data.photo_path) {
          console.log('📸 [PHOTO] Фото захвачено, путь:', response.data.photo_path);
          console.log('📥 [DOWNLOAD] Скачивание фото с сервера...');
          
          // Получаем фото через API
          const photoResponse = await axios.get(`/api${response.data.photo_path}`, {
            responseType: 'blob'
          });

          console.log('✅ [DOWNLOAD] Фото скачано, размер:', photoResponse.data.size, 'bytes');
          const photoUrl = URL.createObjectURL(photoResponse.data);
          setCapturedPhotoUrl(photoUrl);
          console.log('🖼️ [DISPLAY] capturedPhotoUrl установлен:', photoUrl);
          
          // Создаем файл из blob для сохранения
          const file = new File([photoResponse.data], `${newUser.hikvision_id}_face.jpg`, { type: 'image/jpeg' });
          setNewUserPhoto(file);
          
          console.log('✅ [PHOTO] Фото установлено в newUserPhoto:', {
            name: file.name,
            size: file.size,
            type: file.type
          });
        } else if (response.data.can_continue_without_preview) {
          // Фото захвачено на терминале, но предпросмотр недоступен из-за ограничений прав
          console.log('⚠️ [PHOTO] Предпросмотр недоступен, но фото захвачено на терминале');
          setCaptureMessage('✅ Фото захвачено на терминале! (Предпросмотр недоступен из-за прав доступа, но регистрация возможна)');
          
          // Создаем фиктивный файл-заглушку чтобы активировать кнопку "Сохранить"
          const placeholderBlob = new Blob([''], { type: 'image/jpeg' });
          const placeholderFile = new File([placeholderBlob], `${newUser.hikvision_id}_terminal_captured.jpg`, { type: 'image/jpeg' });
          setNewUserPhoto(placeholderFile);
          
          console.log('✅ [PHOTO] Установлен placeholder для активации формы');
        }

        // Фото уже захвачено и загружено на терминал
        setIsCapturingFromTerminal(false);
        console.log('✅ [STATE] Состояние обновлено: isCapturingFromTerminal=false');
      } else {
        throw new Error(response.data.message || 'Не удалось захватить фото');
      }
    } catch (error) {
      console.error('❌ [ERROR] Ошибка при захвате фото:', error);
      setCaptureStatus('error');
      setCaptureMessage('Ошибка: ' + (error.response?.data?.detail || error.message));
      setIsCapturingFromTerminal(false);
    }
  };
  

  // Создание пользователя с автоматической синхронизацией
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!newUserPhoto) {
      alert('Пожалуйста, сделайте фото на терминале или загрузите файл');
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
        console.log('⏭️ [UPLOAD] Пропускаем загрузку фото - используется захваченное на терминале');
        setCreationStep('Используется фото с терминала...');
      }
      
      // Шаг 3: Синхронизация с устройством
      setCreationStep('Синхронизация с терминалом...');
      await axios.post(`/api/users/${userId}/sync-to-device`);
      
      // Успех!
      queryClient.invalidateQueries(['users']);
      setIsModalOpen(false);
      setNewUser({ hikvision_id: '', full_name: '', department: '' });
      setNewUserPhoto(null);
      setCapturedPhotoUrl(null);
      setCreationStep('');
      setCaptureStatus(null);
      setCaptureMessage('');
      alert('Сотрудник успешно добавлен и синхронизирован с терминалом!');
      
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.message;
      alert(`Ошибка: ${errorMsg}`);
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
    onSuccess: () => {
      queryClient.invalidateQueries(['users']);
      alert('Фото успешно загружено!');
      setEditingUser(null);
      setSelectedPhoto(null);
    },
    onError: (error) => {
      alert('Ошибка загрузки фото: ' + (error.response?.data?.detail || error.message));
    }
  });

  // Синхронизация с устройством
  const syncMutation = useMutation({
    mutationFn: (userId) => axios.post(`/api/users/${userId}/sync-to-device`),
    onSuccess: () => {
      queryClient.invalidateQueries(['users']);
      alert('Пользователь успешно синхронизирован с устройством!');
    },
    onError: (error) => {
      alert('Ошибка синхронизации: ' + (error.response?.data?.detail || error.message));
    }
  });

  // Удаление пользователя
  const deleteMutation = useMutation({
    mutationFn: (userId) => axios.delete(`/api/users/${userId}`),
    onSuccess: () => {
      queryClient.invalidateQueries(['users']);
      alert('Пользователь успешно удален!');
    },
    onError: (error) => {
      alert('Ошибка удаления: ' + (error.response?.data?.detail || error.message));
    }
  });

  const handleDelete = (userId, userName) => {
    if (window.confirm(`Вы уверены, что хотите удалить пользователя "${userName}"? Это действие нельзя отменить.`)) {
      deleteMutation.mutate(userId);
    }
  };

  const handlePhotoUpload = (userId) => {
    if (!selectedPhoto) {
      alert('Выберите фото');
      return;
    }
    uploadPhotoMutation.mutate({ userId, file: selectedPhoto });
  };

  const handleSync = (userId) => {
    if (window.confirm('Синхронизировать пользователя с терминалом?')) {
      syncMutation.mutate(userId);
    }
  };

  if (isLoading) return <div className="p-8">Загрузка...</div>;

  // Получаем активное устройство или первое доступное
  const activeDevice = devices?.find(d => d.is_active) || devices?.[0];

  return (
    <div className="px-4 py-6 sm:px-0">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-semibold text-gray-900 tracking-tight">Сотрудники</h1>
        <button
          onClick={() => setIsModalOpen(true)}
          className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 shadow-medium transition-shadow duration-200 font-medium"
        >
          Добавить сотрудника
        </button>
      </div>

      {/* Список пользователей с терминала */}
      {devices && devices.length > 0 && (
        <div className="mb-6 bg-white shadow-card rounded-lg p-4 border border-gray-100">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900 tracking-tight">Пользователи с терминала</h2>
            <div className="flex items-center gap-2">
              <select
                value={selectedDeviceId || ''}
                onChange={(e) => {
                  handleDeviceChange(e.target.value);
                }}
                className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">Выберите устройство</option>
                {devices.map((device) => (
                  <option key={device.id} value={device.id}>
                    {device.name} ({device.ip_address})
                  </option>
                ))}
              </select>
              {selectedDeviceId && (
                <button
                  onClick={() => refetchTerminal()}
                  disabled={isLoadingTerminal}
                  className="bg-gray-100 text-gray-700 px-3 py-2 rounded-md hover:bg-gray-200 text-sm disabled:opacity-50 shadow-soft transition-shadow duration-200 font-medium"
                >
                  {isLoadingTerminal ? 'Загрузка...' : 'Обновить'}
                </button>
              )}
            </div>
          </div>

          {selectedDeviceId ? (
            isLoadingTerminal ? (
              <div className="text-center py-8 text-gray-500">Загрузка пользователей с терминала...</div>
            ) : terminalUsers ? (
              terminalUsers.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          ID
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Имя
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Тип
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Статус фото
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Двери
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {terminalUsers.map((user, index) => {
                        const hasPhoto = user.numOfFace > 0;
                        
                        return (
                          <tr key={user.employeeNo || index} className="hover:bg-gray-50">
                            <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                              {user.employeeNo || 'N/A'}
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                              {user.name || 'Не указано'}
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                              {user.userType || 'normal'}
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                              {hasPhoto ? (
                                <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                                  {user.numOfFace} фото
                                </span>
                              ) : (
                                <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800">
                                  Нет фото
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                              {user.doorRight || 'N/A'}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  <div className="mt-2 text-sm text-gray-500">
                    Всего пользователей: {terminalUsers.length}
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">На терминале нет пользователей</div>
              )
            ) : (
              <div className="text-center py-8 text-red-500">Ошибка загрузки пользователей с терминала</div>
            )
          ) : (
            <div className="text-center py-8 text-gray-400">Выберите устройство для просмотра пользователей</div>
          )}
        </div>
      )}

      {/* Таблица */}
      <div className="bg-white shadow-card overflow-hidden sm:rounded-lg border border-gray-100">
        <ul className="divide-y divide-gray-200">
          {users?.map((user) => (
            <li key={user.id} className="px-4 py-4 sm:px-6 hover:bg-gray-50 transition-colors duration-150">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  {user.photo_path ? (
                    <img 
                      src={`/api${user.photo_path}`}
                      alt={user.full_name}
                      className="h-12 w-12 rounded-full object-cover shadow-soft border-2 border-gray-100"
                    />
                  ) : (
                    <div className="h-12 w-12 rounded-full bg-gray-200 flex items-center justify-center shadow-soft border-2 border-gray-100">
                      <span className="text-gray-500 text-xs font-medium">Нет фото</span>
                    </div>
                  )}
                  <div>
                    <p className="text-sm font-semibold text-gray-900 truncate">{user.full_name}</p>
                    <p className="flex items-center text-sm text-gray-500 mt-0.5">
                      ID: <span className="font-medium text-gray-700 ml-1">{user.hikvision_id}</span> | Отдел: <span className="ml-1">{user.department || 'Не указан'}</span>
                    </p>
                  </div>
                </div>
                <div className="ml-2 flex items-center space-x-2">
                  <span className={`px-2.5 py-1 inline-flex text-xs leading-5 font-semibold rounded-full shadow-soft ${user.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                    {user.is_active ? 'Активен' : 'Неактивен'}
                  </span>
                  {user.synced_to_device && (
                    <span className="px-2.5 py-1 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800 shadow-soft">
                      Синхронизирован
                    </span>
                  )}
                  <button
                    onClick={() => setEditingUser(user)}
                    className="text-indigo-600 hover:text-indigo-900 text-sm font-medium px-2 py-1 rounded hover:bg-indigo-50 transition-colors duration-150"
                  >
                    Фото
                  </button>
                  <button
                    onClick={() => handleSync(user.id)}
                    disabled={!user.photo_path || syncMutation.isPending}
                    className="text-green-600 hover:text-green-900 text-sm font-medium px-2 py-1 rounded hover:bg-green-50 transition-colors duration-150 disabled:text-gray-400 disabled:cursor-not-allowed disabled:hover:bg-transparent"
                  >
                    Синхронизировать
                  </button>
                  <button
                    onClick={() => handleDelete(user.id, user.full_name)}
                    disabled={deleteMutation.isPending}
                    className="text-red-600 hover:text-red-900 text-sm font-medium px-2 py-1 rounded hover:bg-red-50 transition-colors duration-150 disabled:text-gray-400 disabled:cursor-not-allowed disabled:hover:bg-transparent"
                  >
                    {deleteMutation.isPending ? 'Удаление...' : 'Удалить'}
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>


      {/* Модалка редактирования фото */}
      {editingUser && (
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-md w-full p-6 shadow-large border border-gray-200">
            <h2 className="text-lg font-semibold mb-4 text-gray-900 tracking-tight">Загрузка фото для {editingUser.full_name}</h2>
            <FacePhotoUpload
              onPhotoSelect={setSelectedPhoto}
              currentPhoto={editingUser.photo_path ? `/api${editingUser.photo_path}` : null}
            />
            <div className="flex justify-end gap-2 mt-4">
              <button
                type="button"
                onClick={() => {
                  setEditingUser(null);
                  setSelectedPhoto(null);
                }}
                className="bg-gray-200 text-gray-700 px-4 py-2 rounded-md hover:bg-gray-300 shadow-soft transition-shadow duration-200 font-medium"
              >
                Отмена
              </button>
              <button
                onClick={() => handlePhotoUpload(editingUser.id)}
                disabled={!selectedPhoto || uploadPhotoMutation.isPending}
                className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 disabled:bg-gray-400 shadow-medium transition-shadow duration-200 font-medium"
              >
                {uploadPhotoMutation.isPending ? 'Загрузка...' : 'Сохранить'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Модалка добавления пользователя */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-2xl w-full p-6 shadow-large border border-gray-200">
            <h2 className="text-lg font-semibold mb-4 text-gray-900 tracking-tight">Новый сотрудник</h2>
            <form onSubmit={handleSubmit}>
              <div className="grid grid-cols-2 gap-4">
                {/* Левая колонка - данные */}
                <div>
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-gray-700">ID (с терминала)</label>
                    <input
                      type="text"
                      required
                      disabled={isCreating}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border disabled:bg-gray-100"
                      value={newUser.hikvision_id}
                      onChange={(e) => setNewUser({...newUser, hikvision_id: e.target.value})}
                      placeholder="Например: 1001"
                    />
                  </div>
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-gray-700">ФИО</label>
                    <input
                      type="text"
                      required
                      disabled={isCreating}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border disabled:bg-gray-100"
                      value={newUser.full_name}
                      onChange={(e) => setNewUser({...newUser, full_name: e.target.value})}
                    />
                  </div>
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-gray-700">Отдел</label>
                    <input
                      type="text"
                      disabled={isCreating}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border disabled:bg-gray-100"
                      value={newUser.department}
                      onChange={(e) => setNewUser({...newUser, department: e.target.value})}
                    />
                  </div>
                </div>
                
                {/* Правая колонка - фото */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Фото для распознавания лица
                  </label>
                  
                  {/* Кнопка захвата с терминала */}
                  <div className="mb-3">
                    <button
                      type="button"
                      onClick={handleStartFaceCapture}
                      disabled={isCapturingFromTerminal || isCreating || !newUser.hikvision_id}
                      className="w-full bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-medium transition-shadow duration-200 font-medium"
                    >
                      {isCapturingFromTerminal ? (
                        <>
                          <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                          <span>Захват...</span>
                        </>
                      ) : (
                        <>
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                          </svg>
                          <span>Захват с терминала</span>
                        </>
                      )}
                    </button>
                    
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

              <div className="flex justify-end gap-2 mt-4">
                <button
                  type="button"
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
                  className="bg-gray-200 text-gray-700 px-4 py-2 rounded-md hover:bg-gray-300 disabled:bg-gray-100 disabled:cursor-not-allowed shadow-soft transition-shadow duration-200 font-medium"
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  disabled={isCreating || !newUserPhoto}
                  className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed shadow-medium transition-shadow duration-200 font-medium"
                >
                  {isCreating ? 'Создание...' : 'Сохранить и синхронизировать'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default UsersPage;

