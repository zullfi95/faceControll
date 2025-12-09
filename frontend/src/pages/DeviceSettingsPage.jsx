import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';

const DeviceSettingsPage = () => {
  const queryClient = useQueryClient();
  const [isAddingDevice, setIsAddingDevice] = useState(false);
  const [isEditingDevice, setIsEditingDevice] = useState(false);
  const [editingDeviceData, setEditingDeviceData] = useState(null);
  const [newDevice, setNewDevice] = useState({
    name: '',
    ip_address: '',
    username: 'admin',
    password: ''
  });

  // Получение списка устройств
  const { data: devices, isLoading } = useQuery({
    queryKey: ['devices'],
    queryFn: async () => {
      const res = await axios.get('/api/devices/');
      return res.data;
    }
  });

  // Проверка статуса устройства
  const { data: deviceStatus, refetch: checkStatus } = useQuery({
    queryKey: ['device-status', devices?.[0]?.id],
    queryFn: async () => {
      if (!devices || devices.length === 0) return null;
      const res = await axios.get(`/api/devices/${devices[0].id}/status`);
      return res.data;
    },
    enabled: !!devices && devices.length > 0,
    refetchInterval: false
  });

  // Получение поддерживаемых функций
  const { data: supportedFeatures, isLoading: featuresLoading } = useQuery({
    queryKey: ['supported-features', devices?.[0]?.id],
    queryFn: async () => {
      if (!devices || devices.length === 0) return null;
      const res = await axios.get(`/api/devices/${devices[0].id}/supported-features`);
      return res.data;
    },
    enabled: !!devices && devices.length > 0 && deviceStatus?.connected,
    refetchInterval: false
  });

  // Перезагрузка устройства
  const rebootMutation = useMutation({
    mutationFn: (deviceId) => axios.post(`/api/devices/${deviceId}/reboot`),
    onSuccess: () => {
      alert('Команда перезагрузки отправлена! Устройство перезагрузится через несколько секунд.');
    },
    onError: (error) => {
      alert('Ошибка: ' + (error.response?.data?.detail || error.message));
    }
  });

  const handleReboot = () => {
    if (!devices || devices.length === 0) return;
    if (window.confirm('Вы уверены, что хотите перезагрузить устройство? Это может занять несколько минут.')) {
      rebootMutation.mutate(devices[0].id);
    }
  };

  // Создание устройства
  const createMutation = useMutation({
    mutationFn: (device) => axios.post('/api/devices/', device),
    onSuccess: () => {
      queryClient.invalidateQueries(['devices']);
      setIsAddingDevice(false);
      setNewDevice({ name: '', ip_address: '', username: 'admin', password: '' });
      alert('Устройство успешно добавлено!');
    },
    onError: (error) => {
      alert('Ошибка: ' + (error.response?.data?.detail || error.message));
    }
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    createMutation.mutate(newDevice);
  };

  // Обновление устройства
  const updateMutation = useMutation({
    mutationFn: ({ deviceId, data }) => axios.put(`/api/devices/${deviceId}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries(['devices']);
      setIsEditingDevice(false);
      setEditingDeviceData(null);
      alert('Устройство успешно обновлено!');
    },
    onError: (error) => {
      alert('Ошибка: ' + (error.response?.data?.detail || error.message));
    }
  });

  const handleUpdateSubmit = (e) => {
    e.preventDefault();
    const deviceId = devices[0].id;
    updateMutation.mutate({ 
      deviceId, 
      data: {
        name: editingDeviceData.name,
        ip_address: editingDeviceData.ip_address,
        username: editingDeviceData.username,
        password: editingDeviceData.password
      }
    });
  };

  const startEditing = () => {
    setEditingDeviceData({
      name: devices[0].name,
      ip_address: devices[0].ip_address,
      username: devices[0].username,
      password: ''
    });
    setIsEditingDevice(true);
  };

  if (isLoading) return <div className="p-8">Загрузка...</div>;

  return (
    <div className="px-4 py-6 sm:px-0">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Настройки устройства</h1>
        <p className="mt-1 text-sm text-gray-600">
          Конфигурация терминала DS-K1T343EFWX для управления через ISAPI
        </p>
      </div>

      {/* Текущее устройство */}
      {devices && devices.length > 0 ? (
        <div className="bg-white shadow sm:rounded-lg mb-6">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
              {devices[0].name}
            </h3>
            
            <dl className="grid grid-cols-1 gap-x-4 gap-y-4 sm:grid-cols-2">
              <div>
                <dt className="text-sm font-medium text-gray-500">IP адрес</dt>
                <dd className="mt-1 text-sm text-gray-900">{devices[0].ip_address}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Пользователь</dt>
                <dd className="mt-1 text-sm text-gray-900">{devices[0].username}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Статус</dt>
                <dd className="mt-1">
                  <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                    devices[0].is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                  }`}>
                    {devices[0].is_active ? 'Активно' : 'Неактивно'}
                  </span>
                </dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Последняя синхронизация</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {devices[0].last_sync 
                    ? new Date(devices[0].last_sync).toLocaleString('ru-RU')
                    : 'Никогда'}
                </dd>
              </div>
            </dl>

            {/* Проверка соединения */}
            <div className="mt-6 border-t pt-4">
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => checkStatus()}
                  className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700"
                >
                  Проверить соединение
                </button>
                
                <button
                  onClick={startEditing}
                  className="bg-yellow-600 text-white px-4 py-2 rounded-md hover:bg-yellow-700"
                >
                  Редактировать
                </button>

                {deviceStatus?.connected && supportedFeatures?.features?.system?.reboot && (
                  <button
                    onClick={handleReboot}
                    disabled={rebootMutation.isPending}
                    className="bg-red-600 text-white px-4 py-2 rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {rebootMutation.isPending ? 'Перезагрузка...' : 'Перезагрузить устройство'}
                  </button>
                )}
              </div>

              {deviceStatus && (
                <div className="mt-4">
                  {deviceStatus.connected ? (
                    <div className="bg-green-50 border border-green-200 rounded-md p-4">
                      <div className="flex">
                        <div className="flex-shrink-0">
                          <svg className="h-5 w-5 text-green-400" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                          </svg>
                        </div>
                        <div className="ml-3">
                          <h3 className="text-sm font-medium text-green-800">Устройство доступно</h3>
                          {deviceStatus.device_info && (
                            <div className="mt-2 text-sm text-green-700">
                              <p>Модель: {deviceStatus.device_info.model}</p>
                              <p>Серийный номер: {deviceStatus.device_info.serialNumber}</p>
                              <p>Версия ПО: {deviceStatus.device_info.firmwareVersion}</p>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="bg-red-50 border border-red-200 rounded-md p-4">
                      <div className="flex">
                        <div className="flex-shrink-0">
                          <svg className="h-5 w-5 text-red-400" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                          </svg>
                        </div>
                        <div className="ml-3">
                          <h3 className="text-sm font-medium text-red-800">Устройство недоступно</h3>
                          <p className="mt-1 text-sm text-red-700">{deviceStatus.error}</p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Поддерживаемые функции */}
            {deviceStatus?.connected && (
              <div className="mt-6 border-t pt-6">
                <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                  Поддерживаемые функции
                </h3>
                {featuresLoading ? (
                  <p className="text-sm text-gray-500">Загрузка...</p>
                ) : supportedFeatures?.features ? (
                  <div className="space-y-4">
                    {/* Системные функции */}
                    <div>
                      <h4 className="text-sm font-semibold text-gray-700 mb-2">Система</h4>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                        {supportedFeatures.features.system.reboot && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Перезагрузка</span>
                          </div>
                        )}
                        {supportedFeatures.features.system.factory_reset && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Сброс настроек</span>
                          </div>
                        )}
                        {supportedFeatures.features.system.firmware_update && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Обновление прошивки</span>
                          </div>
                        )}
                        {supportedFeatures.features.system.snapshot && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Снимок экрана</span>
                          </div>
                        )}
                        {supportedFeatures.features.system.preview && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Предпросмотр</span>
                          </div>
                        )}
                        {supportedFeatures.features.system.configuration_import && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Импорт конфигурации</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Сеть */}
                    <div>
                      <h4 className="text-sm font-semibold text-gray-700 mb-2">Сеть</h4>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                        {supportedFeatures.features.network.wifi && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Wi-Fi</span>
                          </div>
                        )}
                        {supportedFeatures.features.network.https && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>HTTPS</span>
                          </div>
                        )}
                        {supportedFeatures.features.network.ssh && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>SSH</span>
                          </div>
                        )}
                        {supportedFeatures.features.network.websocket && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>WebSocket</span>
                          </div>
                        )}
                        {supportedFeatures.features.network.ezviz && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>EZVIZ</span>
                          </div>
                        )}
                        {!supportedFeatures.features.network.ddns && (
                          <div className="flex items-center text-sm">
                            <span className="text-red-600 mr-2">✗</span>
                            <span className="text-gray-500">DDNS</span>
                          </div>
                        )}
                        {!supportedFeatures.features.network.ftp && (
                          <div className="flex items-center text-sm">
                            <span className="text-red-600 mr-2">✗</span>
                            <span className="text-gray-500">FTP</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Безопасность */}
                    <div>
                      <h4 className="text-sm font-semibold text-gray-700 mb-2">Безопасность</h4>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                        {supportedFeatures.features.security.user_check && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Проверка пользователей</span>
                          </div>
                        )}
                        {supportedFeatures.features.security.config_import && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Импорт конфигурации</span>
                          </div>
                        )}
                        {supportedFeatures.features.security.config_export && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Экспорт конфигурации</span>
                          </div>
                        )}
                        {supportedFeatures.features.security.certificates && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Сертификаты</span>
                          </div>
                        )}
                        {supportedFeatures.features.security.password_protection && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Защита паролем</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Контроль доступа */}
                    {supportedFeatures.features.access_control.supported && (
                      <div>
                        <h4 className="text-sm font-semibold text-gray-700 mb-2">Контроль доступа</h4>
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Access Control</span>
                          </div>
                          {supportedFeatures.features.access_control.encryption && (
                            <div className="flex items-center text-sm">
                              <span className="text-green-600 mr-2">✓</span>
                              <span>Шифрование</span>
                            </div>
                          )}
                          {supportedFeatures.features.access_control.acs_update && (
                            <div className="flex items-center text-sm">
                              <span className="text-green-600 mr-2">✓</span>
                              <span>Обновление ACS</span>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Видео/Аудио */}
                    <div>
                      <h4 className="text-sm font-semibold text-gray-700 mb-2">Видео/Аудио</h4>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-sm">
                        <div>Видео входов: {supportedFeatures.features.video_audio.video_inputs}</div>
                        <div>Аудио входов: {supportedFeatures.features.video_audio.audio_inputs}</div>
                        <div>Аудио выходов: {supportedFeatures.features.video_audio.audio_outputs}</div>
                        <div>Голосовая связь: {supportedFeatures.features.video_audio.voice_talk} канал</div>
                      </div>
                    </div>

                    {/* Дополнительно */}
                    <div>
                      <h4 className="text-sm font-semibold text-gray-700 mb-2">Дополнительно</h4>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                        {supportedFeatures.features.other.bluetooth && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Bluetooth</span>
                          </div>
                        )}
                        {supportedFeatures.features.other.iot_channels > 0 && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>IOT каналов: {supportedFeatures.features.other.iot_channels}</span>
                          </div>
                        )}
                        {supportedFeatures.features.other.manual_snapshot && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Ручной снимок</span>
                          </div>
                        )}
                        {supportedFeatures.features.other.user_manual_qr && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>QR код пользователя</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">Не удалось загрузить информацию о функциях</p>
                )}
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4 mb-6">
          <p className="text-sm text-yellow-700">
            Устройство не настроено. Добавьте терминал для управления пользователями.
          </p>
        </div>
      )}

      {/* Редактирование устройства */}
      {isEditingDevice && editingDeviceData && (
        <div className="bg-white shadow sm:rounded-lg mb-6">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
              Редактирование устройства
            </h3>
            <form onSubmit={handleUpdateSubmit}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Название</label>
                  <input
                    type="text"
                    required
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border"
                    value={editingDeviceData.name}
                    onChange={(e) => setEditingDeviceData({...editingDeviceData, name: e.target.value})}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">IP адрес</label>
                  <input
                    type="text"
                    required
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border"
                    value={editingDeviceData.ip_address}
                    onChange={(e) => setEditingDeviceData({...editingDeviceData, ip_address: e.target.value})}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Имя пользователя</label>
                  <input
                    type="text"
                    required
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border"
                    value={editingDeviceData.username}
                    onChange={(e) => setEditingDeviceData({...editingDeviceData, username: e.target.value})}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Новый пароль</label>
                  <input
                    type="password"
                    required
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border"
                    value={editingDeviceData.password}
                    onChange={(e) => setEditingDeviceData({...editingDeviceData, password: e.target.value})}
                    placeholder="Введите пароль от терминала"
                  />
                </div>
              </div>
              <div className="mt-6 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setIsEditingDevice(false);
                    setEditingDeviceData(null);
                  }}
                  className="bg-gray-200 text-gray-700 px-4 py-2 rounded hover:bg-gray-300"
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  className="bg-indigo-600 text-white px-4 py-2 rounded hover:bg-indigo-700"
                >
                  Обновить
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Добавление нового устройства */}
      {!isAddingDevice && (!devices || devices.length === 0) && (
        <button
          onClick={() => setIsAddingDevice(true)}
          className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700"
        >
          Добавить устройство
        </button>
      )}

      {isAddingDevice && (
        <div className="bg-white shadow sm:rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
              Новое устройство
            </h3>
            <form onSubmit={handleSubmit}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Название</label>
                  <input
                    type="text"
                    required
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border"
                    value={newDevice.name}
                    onChange={(e) => setNewDevice({...newDevice, name: e.target.value})}
                    placeholder="Например: Терминал Вход"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">IP адрес (в VPN сети)</label>
                  <input
                    type="text"
                    required
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border"
                    value={newDevice.ip_address}
                    onChange={(e) => setNewDevice({...newDevice, ip_address: e.target.value})}
                    placeholder="10.0.0.100"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Имя пользователя</label>
                  <input
                    type="text"
                    required
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border"
                    value={newDevice.username}
                    onChange={(e) => setNewDevice({...newDevice, username: e.target.value})}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Пароль</label>
                  <input
                    type="password"
                    required
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border"
                    value={newDevice.password}
                    onChange={(e) => setNewDevice({...newDevice, password: e.target.value})}
                  />
                </div>
              </div>
              <div className="mt-6 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsAddingDevice(false)}
                  className="bg-gray-200 text-gray-700 px-4 py-2 rounded hover:bg-gray-300"
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  className="bg-indigo-600 text-white px-4 py-2 rounded hover:bg-indigo-700"
                >
                  Сохранить
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Инструкция */}
      <div className="mt-6 bg-blue-50 border border-blue-200 rounded-md p-4">
        <h4 className="text-sm font-medium text-blue-800 mb-2">Важная информация:</h4>
        <ul className="text-sm text-blue-700 space-y-1 list-disc list-inside">
          <li>IP адрес должен быть адресом устройства в VPN сети (например, 10.0.0.100)</li>
          <li>Убедитесь, что ISAPI включен в настройках терминала</li>
          <li>Используйте учетную запись с правами администратора</li>
          <li>После добавления проверьте соединение кнопкой "Проверить соединение"</li>
        </ul>
      </div>
    </div>
  );
};

export default DeviceSettingsPage;

