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
  const [tempPhotoFilename, setTempPhotoFilename] = useState(null);
  const [selectedPhoto, setSelectedPhoto] = useState(null);
  const [editingUser, setEditingUser] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isCapturing, setIsCapturing] = useState(false);
  const [creationStep, setCreationStep] = useState('');
  const [showEnrollmentInstructions, setShowEnrollmentInstructions] = useState(false);
  const [enrollmentInstructions, setEnrollmentInstructions] = useState([]);
  const [enrollmentSuccess, setEnrollmentSuccess] = useState(false);
  
  // Remote enrollment states
  const [showMethodSelection, setShowMethodSelection] = useState(false);
  const [enrollmentMode, setEnrollmentMode] = useState(null); // 'device' | 'interface' | null
  const [pollingInterval, setPollingInterval] = useState(null);
  const [enrollmentTimeout, setEnrollmentTimeout] = useState(60);
  const [timeLeft, setTimeLeft] = useState(60);
  const [enrollmentError, setEnrollmentError] = useState(null);
  const [isEnrolling, setIsEnrolling] = useState(false);
  
  // Face capture from terminal states
  const [isCapturingFromTerminal, setIsCapturingFromTerminal] = useState(false);
  const [captureStatus, setCaptureStatus] = useState(null); // 'waiting' | 'capturing' | 'success' | 'error'
  const [captureMessage, setCaptureMessage] = useState('');

  // Получение пользователей
  const { data: users, isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: async () => {
      const res = await axios.get('/api/users/');
      return res.data;
    }
  });

  // Запуск регистрации лица на терминале
  const handleStartEnrollment = async () => {
    if (!newUser.hikvision_id || !newUser.full_name) {
      alert('Заполните ID и ФИО перед регистрацией!');
      return;
    }
    
    setIsCapturing(true);
    try {
      const response = await axios.post('/api/devices/start-face-enrollment', newUser);
      
      if (response.data.success) {
        setEnrollmentInstructions(response.data.instructions || []);
        setShowEnrollmentInstructions(true);
        setEnrollmentSuccess(false);
      } else {
        alert('Ошибка: ' + response.data.message);
      }
    } catch (error) {
      alert('Ошибка запуска регистрации: ' + (error.response?.data?.detail || error.message));
    } finally {
      setIsCapturing(false);
    }
  };
  
  // Завершение регистрации после того как пользователь зарегистрировался
  const handleCompleteEnrollment = async () => {
    setIsCreating(true);
    setCreationStep('Сохранение данных в систему...');
    
    try {
      // Создаем пользователя в БД (если еще не создан)
      const userCheck = await axios.get(`/api/users/`);
      const existingUser = userCheck.data.find(u => u.hikvision_id === newUser.hikvision_id);
      
      let userId;
      if (!existingUser) {
        const userResponse = await axios.post('/api/users/', newUser);
        userId = userResponse.data.id;
      } else {
        userId = existingUser.id;
      }
      
      // Отмечаем как синхронизированного
      await axios.post(`/api/users/${userId}/sync-to-device`).catch(() => {
        // Игнорируем ошибку синхронизации, т.к. пользователь уже на терминале
      });
      
      // Успех!
      queryClient.invalidateQueries(['users']);
      setIsModalOpen(false);
      setShowEnrollmentInstructions(false);
      setNewUser({ hikvision_id: '', full_name: '', department: '' });
      setNewUserPhoto(null);
      setCapturedPhotoUrl(null);
      setTempPhotoFilename(null);
      setCreationStep('');
      alert('✅ Сотрудник успешно зарегистрирован!');
      
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.message;
      alert(`Ошибка: ${errorMsg}`);
    } finally {
      setIsCreating(false);
    }
  };

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
  
  // Polling для проверки статуса захвата лица
  const startFaceCapturePolling = (deviceId) => {
    let attempts = 0;
    const maxAttempts = 30; // 60 секунд (30 попыток * 2 сек)
    
    const pollInterval = setInterval(async () => {
      attempts++;
      
      try {
        // Проверяем, зарегистрировано ли лицо
        const statusRes = await axios.get(`/api/devices/check-enrollment-status/${newUser.hikvision_id}`);
        
        if (statusRes.data.registered) {
          // Лицо зарегистрировано! Получаем фото
          clearInterval(pollInterval);
          await fetchFaceFromTerminal(deviceId);
        } else if (attempts >= maxAttempts) {
          clearInterval(pollInterval);
          setCaptureStatus('error');
          setCaptureMessage('Время ожидания истекло. Попробуйте снова.');
          setIsCapturingFromTerminal(false);
        }
      } catch (error) {
        console.error('Polling error:', error);
        if (attempts >= maxAttempts) {
          clearInterval(pollInterval);
          setCaptureStatus('error');
          setCaptureMessage('Ошибка проверки статуса');
          setIsCapturingFromTerminal(false);
        }
      }
    }, 2000); // Каждые 2 секунды
  };
  
  // Получение фото лица с терминала
  const fetchFaceFromTerminal = async (deviceId) => {
    try {
      setCaptureMessage('Получение фото с терминала...');
      
      // Получаем фото через UserFace/faceData
      const faceDataRes = await axios.get(`/api/devices/${deviceId}/user-face-data`, {
        params: { employee_no: newUser.hikvision_id },
        responseType: 'blob'
      });
      
      // Создаем файл из blob
      const blob = faceDataRes.data;
      const file = new File([blob], `${newUser.hikvision_id}_face.jpg`, { type: 'image/jpeg' });
      setNewUserPhoto(file);
      
      // Создаем URL для предпросмотра
      const imageUrl = URL.createObjectURL(blob);
      setCapturedPhotoUrl(imageUrl);
      
      setCaptureStatus('success');
      setCaptureMessage('✅ Фото успешно получено с терминала! Проверьте изображение и нажмите "Сохранить".');
      setIsCapturingFromTerminal(false);
      
    } catch (error) {
      setCaptureStatus('error');
      setCaptureMessage('Ошибка получения фото: ' + (error.response?.data?.detail || error.message));
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
      
      // Шаг 2: Загрузка фото
      setCreationStep('Загрузка фото...');
      const formData = new FormData();
      formData.append('file', newUserPhoto);
      await axios.post(`/api/users/${userId}/upload-photo`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      // Шаг 3: Синхронизация с устройством
      setCreationStep('Синхронизация с терминалом...');
      await axios.post(`/api/users/${userId}/sync-to-device`);
      
      // Успех!
      queryClient.invalidateQueries(['users']);
      setIsModalOpen(false);
      setNewUser({ hikvision_id: '', full_name: '', department: '' });
      setNewUserPhoto(null);
      setCapturedPhotoUrl(null);
      setTempPhotoFilename(null);
      setCreationStep('');
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

  // Remote enrollment functions
  const handleSelectMethod = (method) => {
    setShowMethodSelection(false);
    
    if (method === 'interface') {
      // Открыть существующую форму регистрации с интерфейса
      setEnrollmentMode(null); // Сбрасываем режим устройства
      setIsModalOpen(true);
    } else if (method === 'device') {
      // Режим регистрации с устройства
      setEnrollmentMode('device');
      setIsModalOpen(false); // Закрываем модалку интерфейса, если была открыта
    }
  };

  const handleStartRemoteEnrollment = async () => {
    console.log('🚀 [START] handleStartRemoteEnrollment вызван');
    console.log('📋 [DATA] newUser:', newUser);
    
    // Валидация
    if (!newUser.hikvision_id || !newUser.full_name) {
      console.warn('⚠️ [VALIDATION] Не заполнены ID или ФИО');
      alert('Заполните ID и ФИО!');
      return;
    }

    // Проверка дубликата
    const existingUser = users?.find(u => u.hikvision_id === newUser.hikvision_id);
    if (existingUser) {
      console.warn('⚠️ [VALIDATION] Пользователь уже существует:', existingUser);
      setEnrollmentError('Пользователь с таким ID уже зарегистрирован');
      return;
    }

    console.log('✅ [VALIDATION] Валидация пройдена');
    setIsEnrolling(true);
    setEnrollmentError(null);

    try {
      // Получаем device_id (берем первый активный)
      console.log('🔍 [DEVICE] Получение списка устройств...');
      const devicesRes = await axios.get('/api/devices/');
      const device = devicesRes.data.find(d => d.is_active) || devicesRes.data[0];
      
      if (!device) {
        throw new Error('Устройство не найдено');
      }
      
      console.log('✅ [DEVICE] Устройство найдено:', device.id, device.name);

      // Используем правильный endpoint с CaptureFaceData
      console.log('📤 [REQUEST] Отправка запроса на захват фото...');
      const response = await axios.post(`/api/devices/${device.id}/start-face-capture`, {
        employee_no: newUser.hikvision_id,
        hikvision_id: newUser.hikvision_id,
        full_name: newUser.full_name
      });

      console.log('📥 [RESPONSE] Ответ получен:', {
        success: response.data.success,
        photo_path: response.data.photo_path,
        face_data_url: response.data.face_data_url,
        capture_progress: response.data.capture_progress
      });

      if (response.data.success) {
        // Проверяем, есть ли уже захваченное фото
        if (response.data.photo_path) {
          console.log('📸 [PHOTO] Фото уже захвачено, путь:', response.data.photo_path);
          // Фото уже захвачено и скачано!
          try {
            // Получаем фото через API
            console.log('📥 [DOWNLOAD] Скачивание фото с сервера...');
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
            
            // Останавливаем процесс регистрации и показываем фото в форме
            setIsEnrolling(false);
            setCreationStep('Фото успешно захвачено! Проверьте фото и нажмите "Сохранить"');
            
            console.log('✅ [STATE] Состояние обновлено: isEnrolling=false, форма должна показаться');
            
            // НЕ вызываем handleCompleteRemoteEnrollment автоматически
            // Пользователь должен увидеть фото и нажать "Сохранить"
          } catch (photoError) {
            console.error('❌ [ERROR] Ошибка загрузки фото:', photoError);
            setEnrollmentError('Фото захвачено, но не удалось загрузить. Попробуйте снова.');
            setIsEnrolling(false);
          }
        } else if (response.data.face_data_url && response.data.capture_progress === "100") {
          // Фото захвачено, но еще не скачано - скачиваем
          setCreationStep('Скачивание фото с терминала...');
          // Polling будет проверять статус и скачивать фото
          setTimeLeft(enrollmentTimeout);
          startPolling();
        } else {
          // Режим захвата запущен, но фото еще не захвачено - ждем
          setTimeLeft(enrollmentTimeout);
          startPolling();
        }
      } else {
        setEnrollmentError('Не удалось запустить регистрацию на терминале');
        setIsEnrolling(false);
      }
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.message;
      setEnrollmentError(errorMsg);
      setIsEnrolling(false);
    }
  };

  const startPolling = () => {
    let countdown = enrollmentTimeout;
    
    // Таймер обратного отсчета
    const countdownInterval = setInterval(() => {
      countdown -= 1;
      setTimeLeft(countdown);
      
      if (countdown <= 0) {
        clearInterval(countdownInterval);
        if (pollingInterval) {
          clearInterval(pollingInterval);
        }
        setIsEnrolling(false);
        setEnrollmentError('Время ожидания истекло. Попробуйте снова.');
      }
    }, 1000);

    // Polling статуса регистрации
    const pollInterval = setInterval(async () => {
      try {
        const response = await axios.get(`/api/devices/check-enrollment-status/${newUser.hikvision_id}`);
        
        if (response.data.registered) {
          clearInterval(pollInterval);
          clearInterval(countdownInterval);
          await handleCompleteRemoteEnrollment();
        }
      } catch (error) {
        console.error('Polling error:', error);
      }
    }, 2000); // Каждые 2 секунды

    setPollingInterval(pollInterval);
  };

  const handleCompleteRemoteEnrollment = async () => {
    setCreationStep('Завершение регистрации...');
    
    try {
      setIsCreating(true);
      
      console.log('💾 Начало сохранения:', {
        hikvision_id: newUser.hikvision_id,
        full_name: newUser.full_name,
        hasPhoto: !!newUserPhoto,
        photoName: newUserPhoto?.name,
        photoSize: newUserPhoto?.size
      });
      
      // Шаг 1: Создание пользователя в БД
      setCreationStep('Создание пользователя в системе...');
      let userId;
      const existingUser = users?.find(u => u.hikvision_id === newUser.hikvision_id);
      
      if (existingUser) {
        userId = existingUser.id;
        setCreationStep('Пользователь уже существует, обновление данных...');
        console.log('📝 Пользователь уже существует, ID:', userId);
      } else {
        const userResponse = await axios.post('/api/users/', newUser);
        userId = userResponse.data.id;
        console.log('✅ Пользователь создан, ID:', userId);
      }
      
      // Шаг 2: Загрузка фото (если есть)
      if (newUserPhoto) {
        setCreationStep('Загрузка фото...');
        console.log('📤 Загрузка фото:', newUserPhoto.name, newUserPhoto.size, 'bytes');
        const formData = new FormData();
        formData.append('file', newUserPhoto);
        await axios.post(`/api/users/${userId}/upload-photo`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        console.log('✅ Фото загружено успешно');
      } else {
        console.warn('⚠️ Фото отсутствует! newUserPhoto:', newUserPhoto);
        setEnrollmentError('Фото не найдено. Пожалуйста, захватите фото с терминала или загрузите файл.');
        setIsCreating(false);
        return;
      }
      
      // Шаг 3: Синхронизация с устройством
      setCreationStep('Синхронизация с терминалом...');
      await axios.post(`/api/users/${userId}/sync-to-device`).catch((syncError) => {
        console.warn('⚠️ Ошибка синхронизации (игнорируется):', syncError);
        // Игнорируем ошибку синхронизации, т.к. пользователь уже на терминале
      });

      // Успех!
      console.log('✅ Регистрация завершена успешно!');
      queryClient.invalidateQueries(['users']);
      setEnrollmentSuccess(true);
      setIsEnrolling(false);
      setIsCreating(false);
      
      // Автозакрытие через 2 секунды
      setTimeout(() => {
        handleCloseRemoteEnrollment();
      }, 2000);
      
    } catch (error) {
      console.error('❌ Ошибка при сохранении:', error);
      const errorMsg = error.response?.data?.detail || error.message;
      setEnrollmentError(`Ошибка завершения: ${errorMsg}`);
      setIsEnrolling(false);
      setIsCreating(false);
    }
  };

  const handleCancelEnrollment = () => {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      setPollingInterval(null);
    }
    setIsEnrolling(false);
    setEnrollmentError(null);
    handleCloseRemoteEnrollment();
  };

  const handleRetryEnrollment = () => {
    setEnrollmentError(null);
    setTimeLeft(enrollmentTimeout);
    handleStartRemoteEnrollment();
  };

  const handleCloseRemoteEnrollment = () => {
    setEnrollmentMode(null);
    setIsEnrolling(false);
    setEnrollmentError(null);
    setEnrollmentSuccess(false);
    setNewUser({ hikvision_id: '', full_name: '', department: '' });
    setTimeLeft(enrollmentTimeout);
    setCreationStep('');
    setCapturedPhotoUrl(null);
    setNewUserPhoto(null);
    if (pollingInterval) {
      clearInterval(pollingInterval);
      setPollingInterval(null);
    }
  };

  // Cleanup polling on unmount
  React.useEffect(() => {
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    };
  }, [pollingInterval]);

  if (isLoading) return <div className="p-8">Загрузка...</div>;

  return (
    <div className="px-4 py-6 sm:px-0">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Сотрудники</h1>
        <button
          onClick={() => setShowMethodSelection(true)}
          className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700"
        >
          Добавить сотрудника
        </button>
      </div>

      {/* Таблица */}
      <div className="bg-white shadow overflow-hidden sm:rounded-md">
        <ul className="divide-y divide-gray-200">
          {users?.map((user) => (
            <li key={user.id} className="px-4 py-4 sm:px-6 hover:bg-gray-50">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  {user.photo_path ? (
                    <img 
                      src={`/api${user.photo_path}`}
                      alt={user.full_name}
                      className="h-12 w-12 rounded-full object-cover"
                    />
                  ) : (
                    <div className="h-12 w-12 rounded-full bg-gray-200 flex items-center justify-center">
                      <span className="text-gray-500 text-xs">Нет фото</span>
                    </div>
                  )}
                  <div>
                    <p className="text-sm font-medium text-indigo-600 truncate">{user.full_name}</p>
                    <p className="flex items-center text-sm text-gray-500">
                      ID: {user.hikvision_id} | Отдел: {user.department || 'Не указан'}
                    </p>
                  </div>
                </div>
                <div className="ml-2 flex items-center space-x-2">
                  <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${user.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                    {user.is_active ? 'Активен' : 'Неактивен'}
                  </span>
                  {user.synced_to_device && (
                    <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">
                      Синхронизирован
                    </span>
                  )}
                  <button
                    onClick={() => setEditingUser(user)}
                    className="text-indigo-600 hover:text-indigo-900 text-sm"
                  >
                    Фото
                  </button>
                  <button
                    onClick={() => handleSync(user.id)}
                    disabled={!user.photo_path || syncMutation.isPending}
                    className="text-green-600 hover:text-green-900 text-sm disabled:text-gray-400 disabled:cursor-not-allowed"
                  >
                    Синхронизировать
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>

      {/* Модалка выбора способа регистрации */}
      {showMethodSelection && (
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-2xl w-full p-6">
            <h2 className="text-2xl font-bold mb-6 text-center">Выберите способ регистрации</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Регистрация с устройства */}
              <button
                onClick={() => handleSelectMethod('device')}
                className="p-6 border-2 border-gray-300 rounded-lg hover:border-indigo-500 hover:bg-indigo-50 transition-all group"
              >
                <div className="text-center">
                  <div className="text-5xl mb-4">🖥️</div>
                  <h3 className="text-lg font-semibold mb-2 group-hover:text-indigo-600">С устройства</h3>
                  <p className="text-sm text-gray-600">
                    Сотрудник регистрируется прямо на терминале. Фото получается автоматически.
                  </p>
                </div>
              </button>

              {/* Регистрация с интерфейса */}
              <button
                onClick={() => handleSelectMethod('interface')}
                className="p-6 border-2 border-gray-300 rounded-lg hover:border-indigo-500 hover:bg-indigo-50 transition-all group"
              >
                <div className="text-center">
                  <div className="text-5xl mb-4">📝</div>
                  <h3 className="text-lg font-semibold mb-2 group-hover:text-indigo-600">С интерфейса</h3>
                  <p className="text-sm text-gray-600">
                    Ручной ввод данных и загрузка фото с компьютера.
                  </p>
                </div>
              </button>
            </div>

            <div className="flex justify-end mt-6">
              <button
                onClick={() => setShowMethodSelection(false)}
                className="bg-gray-200 text-gray-700 px-4 py-2 rounded hover:bg-gray-300"
              >
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Модалка регистрации с устройства */}
      {enrollmentMode === 'device' && (
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-2xl w-full p-6">
            <h2 className="text-lg font-bold mb-4">Регистрация с устройства</h2>

            {!isEnrolling && !enrollmentSuccess && !enrollmentError && !capturedPhotoUrl && (
              <div>
                {/* Форма ввода данных */}
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">ID сотрудника</label>
                    <input
                      type="text"
                      required
                      value={newUser.hikvision_id}
                      onChange={(e) => setNewUser({...newUser, hikvision_id: e.target.value})}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border"
                      placeholder="Например: 1001"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">ФИО</label>
                    <input
                      type="text"
                      required
                      value={newUser.full_name}
                      onChange={(e) => setNewUser({...newUser, full_name: e.target.value})}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Отдел (опционально)</label>
                    <input
                      type="text"
                      value={newUser.department}
                      onChange={(e) => setNewUser({...newUser, department: e.target.value})}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border"
                    />
                  </div>
                </div>

                <div className="flex justify-end gap-2 mt-6">
                  <button
                    onClick={handleCloseRemoteEnrollment}
                    className="bg-gray-200 text-gray-700 px-4 py-2 rounded hover:bg-gray-300"
                  >
                    Отмена
                  </button>
                  <button
                    onClick={handleStartRemoteEnrollment}
                    className="bg-indigo-600 text-white px-4 py-2 rounded hover:bg-indigo-700"
                  >
                    Запустить регистрацию на терминале
                  </button>
                </div>
              </div>
            )}

            {/* Показываем форму с фото после захвата */}
            {!isEnrolling && !enrollmentSuccess && !enrollmentError && capturedPhotoUrl && (
              <div>
                <div className="mb-4">
                  <p className="text-sm text-green-600 font-medium mb-2">✅ Фото успешно захвачено с терминала!</p>
                  {creationStep && (
                    <p className="text-sm text-gray-600 mb-4">{creationStep}</p>
                  )}
                </div>

                {/* Отображение захваченного фото */}
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">Захваченное фото:</label>
                  <div className="border-2 border-indigo-300 rounded-lg p-4 bg-gray-50">
                    <img
                      src={capturedPhotoUrl}
                      alt="Захваченное фото"
                      className="max-w-full h-auto max-h-64 mx-auto rounded-lg shadow-md"
                    />
                  </div>
                </div>

                {/* Форма с данными (можно редактировать) */}
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">ID сотрудника</label>
                    <input
                      type="text"
                      required
                      value={newUser.hikvision_id}
                      onChange={(e) => setNewUser({...newUser, hikvision_id: e.target.value})}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border"
                      placeholder="Например: 1001"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">ФИО</label>
                    <input
                      type="text"
                      required
                      value={newUser.full_name}
                      onChange={(e) => setNewUser({...newUser, full_name: e.target.value})}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Отдел (опционально)</label>
                    <input
                      type="text"
                      value={newUser.department}
                      onChange={(e) => setNewUser({...newUser, department: e.target.value})}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border"
                    />
                  </div>
                </div>

                <div className="flex justify-end gap-2 mt-6">
                  <button
                    onClick={() => {
                      setCapturedPhotoUrl(null);
                      setNewUserPhoto(null);
                      setCreationStep('');
                    }}
                    className="bg-gray-200 text-gray-700 px-4 py-2 rounded hover:bg-gray-300"
                  >
                    Захватить заново
                  </button>
                  <button
                    onClick={handleCloseRemoteEnrollment}
                    className="bg-gray-200 text-gray-700 px-4 py-2 rounded hover:bg-gray-300"
                  >
                    Отмена
                  </button>
                  <button
                    onClick={() => {
                      console.log('💾 [BUTTON] Кнопка "Сохранить" нажата');
                      console.log('📋 [STATE] Состояние перед сохранением:', {
                        hikvision_id: newUser.hikvision_id,
                        full_name: newUser.full_name,
                        hasPhoto: !!newUserPhoto,
                        photoName: newUserPhoto?.name,
                        photoSize: newUserPhoto?.size,
                        isCreating
                      });
                      handleCompleteRemoteEnrollment();
                    }}
                    disabled={!newUser.hikvision_id || !newUser.full_name || !newUserPhoto || isCreating}
                    className="bg-indigo-600 text-white px-4 py-2 rounded hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
                  >
                    {isCreating ? 'Сохранение...' : 'Сохранить'}
                  </button>
                </div>
              </div>
            )}

            {isEnrolling && !enrollmentSuccess && (
              <div>
                {/* Ожидание регистрации */}
                <div className="text-center py-6">
                  <div className="text-4xl mb-4">⏳</div>
                  <p className="text-lg font-medium mb-2">Ожидание регистрации...</p>
                  <p className="text-sm text-gray-600 mb-4">
                    Подойдите к терминалу и посмотрите в камеру
                  </p>
                  
                  {/* Таймер */}
                  <div className="mb-4">
                    <div className="text-3xl font-bold text-indigo-600">{timeLeft} сек</div>
                  </div>

                  {/* Прогресс-бар */}
                  <div className="w-full bg-gray-200 rounded-full h-2 mb-6">
                    <div 
                      className="bg-indigo-600 h-2 rounded-full transition-all duration-1000"
                      style={{ width: `${(timeLeft / enrollmentTimeout) * 100}%` }}
                    ></div>
                  </div>

                  {creationStep && (
                    <p className="text-sm text-gray-500 mb-4">{creationStep}</p>
                  )}
                </div>

                <div className="flex justify-center">
                  <button
                    onClick={handleCancelEnrollment}
                    className="bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700"
                  >
                    Отменить
                  </button>
                </div>
              </div>
            )}

            {enrollmentSuccess && (
              <div className="text-center py-6">
                <div className="text-5xl mb-4">✅</div>
                <p className="text-lg font-bold text-green-600 mb-2">Регистрация завершена!</p>
                <p className="text-sm text-gray-600">Сотрудник успешно добавлен в систему</p>
              </div>
            )}

            {enrollmentError && !isEnrolling && (
              <div className="text-center py-6">
                <div className="text-5xl mb-4">⚠️</div>
                <p className="text-lg font-bold text-red-600 mb-2">Ошибка регистрации</p>
                <div className="text-sm text-gray-600 mb-6 space-y-2">
                  <p>{enrollmentError}</p>
                  {enrollmentError.includes('не поддерживается') || enrollmentError.includes('not supported') ? (
                    <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded">
                      <p className="font-medium text-blue-800 mb-2">💡 Альтернативное решение:</p>
                      <p className="text-blue-700 text-xs">
                        Используйте способ "Регистрация с интерфейса" для добавления сотрудника вручную.
                      </p>
                    </div>
                  ) : null}
                </div>
                
                <div className="flex justify-center gap-3">
                  <button
                    onClick={handleCloseRemoteEnrollment}
                    className="bg-gray-200 text-gray-700 px-4 py-2 rounded hover:bg-gray-300"
                  >
                    Закрыть
                  </button>
                  {!(enrollmentError.includes('не поддерживается') || enrollmentError.includes('not supported')) && (
                    <button
                      onClick={handleRetryEnrollment}
                      className="bg-indigo-600 text-white px-4 py-2 rounded hover:bg-indigo-700"
                    >
                      Повторить попытку
                    </button>
                  )}
                  {(enrollmentError.includes('не поддерживается') || enrollmentError.includes('not supported')) && (
                    <button
                      onClick={() => {
                        handleCloseRemoteEnrollment();
                        setShowMethodSelection(true);
                      }}
                      className="bg-indigo-600 text-white px-4 py-2 rounded hover:bg-indigo-700"
                    >
                      Выбрать другой способ
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Модалка редактирования фото */}
      {editingUser && (
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-md w-full p-6">
            <h2 className="text-lg font-bold mb-4">Загрузка фото для {editingUser.full_name}</h2>
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
                className="bg-gray-200 text-gray-700 px-4 py-2 rounded hover:bg-gray-300"
              >
                Отмена
              </button>
              <button
                onClick={() => handlePhotoUpload(editingUser.id)}
                disabled={!selectedPhoto || uploadPhotoMutation.isPending}
                className="bg-indigo-600 text-white px-4 py-2 rounded hover:bg-indigo-700 disabled:bg-gray-400"
              >
                {uploadPhotoMutation.isPending ? 'Загрузка...' : 'Сохранить'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Модалка добавления пользователя (регистрация с интерфейса) */}
      {isModalOpen && enrollmentMode !== 'device' && (
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-2xl w-full p-6">
            <h2 className="text-lg font-bold mb-4">Новый сотрудник</h2>
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
                      className="w-full bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center justify-center gap-2"
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
                    setTempPhotoFilename(null);
                    setCaptureStatus(null);
                    setCaptureMessage('');
                    setIsCapturingFromTerminal(false);
                  }}
                  disabled={isCreating}
                  className="bg-gray-200 text-gray-700 px-4 py-2 rounded hover:bg-gray-300 disabled:bg-gray-100 disabled:cursor-not-allowed"
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  disabled={isCreating || !newUserPhoto}
                  className="bg-indigo-600 text-white px-4 py-2 rounded hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
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

