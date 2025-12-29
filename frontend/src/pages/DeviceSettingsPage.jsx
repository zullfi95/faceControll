import React, { useState, useMemo, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import Input from '../components/ui/Input';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import Badge from '../components/ui/Badge';
import Skeleton from '../components/ui/Skeleton';
import showToast from '../utils/toast';
import { MapPinIcon, ChevronDownIcon, ChevronUpIcon } from '@heroicons/react/24/outline';

const DeviceSettingsPage = () => {
  const queryClient = useQueryClient();
  const [isAddingDevice, setIsAddingDevice] = useState(false);
  const [isEditingDevice, setIsEditingDevice] = useState(false);
  const [editingDeviceId, setEditingDeviceId] = useState(null);
  const [editingDeviceData, setEditingDeviceData] = useState(null);
  const [expandedLocations, setExpandedLocations] = useState(new Set());
  const [selectedDeviceId, setSelectedDeviceId] = useState(null);
  const [newDevice, setNewDevice] = useState({
    name: '',
    ip_address: '',
    username: 'admin',
    password: '',
    device_type: 'other',
    location: '',
    priority: 0
  });

  // Получение списка устройств
  const { data: devices, isLoading } = useQuery({
    queryKey: ['devices'],
    queryFn: async () => {
      const res = await axios.get('/api/devices/');
      return res.data;
    }
  });

  // Получение статусов всех устройств
  const { data: devicesStatus, refetch: refetchStatuses } = useQuery({
    queryKey: ['devices-status'],
    queryFn: async () => {
      const res = await axios.get('/api/devices/status');
      return res.data;
    },
    enabled: !!devices && devices.length > 0,
    refetchInterval: 30000 // Обновляем каждые 30 секунд
  });

  // Проверка статуса устройства
  const { data: deviceStatus, refetch: checkStatus } = useQuery({
    queryKey: ['device-status', selectedDeviceId],
    queryFn: async () => {
      if (!selectedDeviceId) return null;
      const res = await axios.get(`/api/devices/${selectedDeviceId}/status`);
      return res.data;
    },
    enabled: !!selectedDeviceId,
    refetchInterval: false
  });

  // Получение поддерживаемых функций
  const { data: supportedFeatures, isLoading: featuresLoading } = useQuery({
    queryKey: ['supported-features', selectedDeviceId],
    queryFn: async () => {
      if (!selectedDeviceId) return null;
      const res = await axios.get(`/api/devices/${selectedDeviceId}/supported-features`);
      return res.data;
    },
    enabled: !!selectedDeviceId && deviceStatus?.connected,
    refetchInterval: false
  });

  // Группировка устройств по локациям
  const devicesByLocation = useMemo(() => {
    if (!devices || devices.length === 0) return {};
    
    const grouped = {};
    devices.forEach(device => {
      const location = device.location?.trim() || 'Без локации';
      if (!grouped[location]) {
        grouped[location] = [];
      }
      grouped[location].push(device);
    });
    
    // Сортируем устройства в каждой группе по приоритету и имени
    Object.keys(grouped).forEach(location => {
      grouped[location].sort((a, b) => {
        if (a.priority !== b.priority) {
          return (b.priority || 0) - (a.priority || 0);
        }
        return a.name.localeCompare(b.name);
      });
    });
    
    return grouped;
  }, [devices]);

  // Автоматически разворачиваем первую локацию при загрузке
  useEffect(() => {
    if (devices && devices.length > 0 && expandedLocations.size === 0) {
      const firstLocation = Object.keys(devicesByLocation)[0];
      if (firstLocation) {
        setExpandedLocations(new Set([firstLocation]));
        // Выбираем первое устройство
        const firstDevice = devicesByLocation[firstLocation][0];
        if (firstDevice) {
          setSelectedDeviceId(firstDevice.id);
        }
      }
    }
  }, [devices, devicesByLocation, expandedLocations.size]);

  // Переключение развернутости локации
  const toggleLocation = (location) => {
    setExpandedLocations(prev => {
      const newSet = new Set(prev);
      if (newSet.has(location)) {
        newSet.delete(location);
      } else {
        newSet.add(location);
      }
      return newSet;
    });
  };

  // Перезагрузка устройства
  const [rebootConfirm, setRebootConfirm] = useState(false);

  const rebootMutation = useMutation({
    mutationFn: (deviceId) => axios.post(`/api/devices/${deviceId}/reboot`),
    onSuccess: () => {
      showToast.success('Команда перезагрузки отправлена! Устройство перезагрузится через несколько секунд.');
    },
    onError: (error) => {
      showToast.error('Ошибка: ' + (error.response?.data?.detail || error.message));
    }
  });

  const handleReboot = (deviceId) => {
    setSelectedDeviceId(deviceId);
    setRebootConfirm(true);
  };

  // Переподключение к устройству
  const reconnectMutation = useMutation({
    mutationFn: (deviceId) => axios.post(`/api/devices/${deviceId}/reconnect`),
    onSuccess: () => {
      queryClient.invalidateQueries(['devices-status']);
      showToast.success('Переподключение выполнено успешно!');
    },
    onError: (error) => {
      showToast.error('Ошибка переподключения: ' + (error.response?.data?.detail || error.message));
    }
  });

  // Создание устройства
  const createMutation = useMutation({
    mutationFn: (device) => axios.post('/api/devices/', device),
    onSuccess: () => {
      queryClient.invalidateQueries(['devices']);
      setIsAddingDevice(false);
      setNewDevice({ name: '', ip_address: '', username: 'admin', password: '' });
      showToast.success('Устройство успешно добавлено!');
    },
    onError: (error) => {
      showToast.error('Ошибка: ' + (error.response?.data?.detail || error.message));
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
      queryClient.invalidateQueries(['devices-status']);
      setIsEditingDevice(false);
      setEditingDeviceId(null);
      setEditingDeviceData(null);
      showToast.success('Устройство успешно обновлено!');
    },
    onError: (error) => {
      showToast.error('Ошибка: ' + (error.response?.data?.detail || error.message));
    }
  });

  const handleUpdateSubmit = (e) => {
    e.preventDefault();
    if (!editingDeviceId) return;
    
    // Подготовка данных - исключаем пароль если он пустой
    const updateData = {
      name: editingDeviceData.name,
      ip_address: editingDeviceData.ip_address,
      username: editingDeviceData.username,
      device_type: editingDeviceData.device_type,
      location: editingDeviceData.location,
      priority: editingDeviceData.priority || 0
    };
    
    // Добавляем пароль только если он указан
    if (editingDeviceData.password && editingDeviceData.password.trim() !== '') {
      updateData.password = editingDeviceData.password;
    }
    
    updateMutation.mutate({ 
      deviceId: editingDeviceId, 
      data: updateData
    });
  };

  const startEditing = (device) => {
    setEditingDeviceId(device.id);
    setEditingDeviceData({
      name: device.name,
      ip_address: device.ip_address,
      username: device.username,
      password: '',
      device_type: device.device_type || 'other',
      location: device.location || '',
      priority: device.priority || 0
    });
    setIsEditingDevice(true);
  };

  const handleDeviceSelect = (deviceId) => {
    setSelectedDeviceId(deviceId);
    // Разворачиваем локацию, если она свернута
    const device = devices?.find(d => d.id === deviceId);
    if (device) {
      const location = device.location?.trim() || 'Без локации';
      if (!expandedLocations.has(location)) {
        setExpandedLocations(prev => new Set([...prev, location]));
      }
    }
  };

  // Безопасные объекты для поддерживаемых функций
  const features = supportedFeatures?.features || {};
  const system = features.system || {};
  const network = features.network || {};
  const security = features.security || {};
  const access = features.access_control || {};
  const videoAudio = features.video_audio || {};
  const other = features.other || {};

  // Получение выбранного устройства
  const selectedDevice = devices?.find(d => d.id === selectedDeviceId);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Card>
          <div className="space-y-4">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div role="main">
      <header className="mb-6 flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900" id="device-settings-title">
            Настройки терминалов
          </h1>
          <p className="mt-1 text-sm text-gray-600" id="device-settings-description">
            Управление терминалами распознавания лиц, сгруппированными по локациям
          </p>
        </div>
        {!isAddingDevice && !isEditingDevice && (
          <Button onClick={() => setIsAddingDevice(true)}>
            + Добавить терминал
          </Button>
        )}
      </header>

      {/* Группировка по локациям */}
      {devices && devices.length > 0 ? (
        <div className="space-y-4 mb-6">
          {Object.entries(devicesByLocation).map(([location, locationDevices]) => {
            const isExpanded = expandedLocations.has(location);
            const activeCount = locationDevices.filter(d => d.is_active).length;
            
            return (
              <Card key={location} className="overflow-hidden">
                <button
                  onClick={() => toggleLocation(location)}
                  className="w-full flex items-center justify-between p-4 hover:bg-gray-50 transition-colors"
                  aria-expanded={isExpanded}
                >
                  <div className="flex items-center gap-3">
                    <MapPinIcon className="h-5 w-5 text-gray-500" />
                    <div className="text-left">
                      <h3 className="text-lg font-semibold text-gray-900">
                        {location}
                      </h3>
                      <p className="text-sm text-gray-500">
                        {locationDevices.length} терминал{locationDevices.length !== 1 ? 'ов' : ''} 
                        {activeCount > 0 && ` • ${activeCount} активн${activeCount !== 1 ? 'ых' : 'ый'}`}
                      </p>
                    </div>
                  </div>
                  {isExpanded ? (
                    <ChevronUpIcon className="h-5 w-5 text-gray-400" />
                  ) : (
                    <ChevronDownIcon className="h-5 w-5 text-gray-400" />
                  )}
                </button>
                
                {isExpanded && (
                  <div className="border-t bg-gray-50">
                    <div className="p-4 space-y-3">
                      {locationDevices.map(device => {
                        const isSelected = selectedDeviceId === device.id;
                        const deviceStatusInfo = devicesStatus?.find(s => s.device_id === device.id);
                        
                        return (
                          <div
                            key={device.id}
                            className={`p-4 bg-white rounded-lg border-2 transition-all cursor-pointer ${
                              isSelected 
                                ? 'border-blue-500 shadow-md' 
                                : 'border-gray-200 hover:border-gray-300'
                            }`}
                            onClick={() => handleDeviceSelect(device.id)}
                          >
                            <div className="flex items-start justify-between">
                              <div className="flex-1">
                                <div className="flex items-center gap-2 mb-2">
                                  <h4 className="font-semibold text-gray-900">{device.name}</h4>
                                  <Badge variant={device.is_active ? 'success' : 'error'}>
                                    {device.is_active ? 'Активен' : 'Неактивен'}
                                  </Badge>
                                  <Badge variant="info">
                                    {device.device_type === 'entry' ? '🚪 Вход' :
                                     device.device_type === 'exit' ? '🚶 Выход' :
                                     device.device_type === 'both' ? '🔄 Оба' :
                                     '📍 Другое'}
                                  </Badge>
                                </div>
                                <div className="grid grid-cols-2 gap-2 text-sm text-gray-600">
                                  <div>
                                    <span className="font-medium">IP:</span> {device.ip_address}
                                  </div>
                                  <div>
                                    <span className="font-medium">Пользователь:</span> {device.username}
                                  </div>
                                  {deviceStatusInfo && (
                                    <div className="col-span-2">
                                      <span className="font-medium">Подписка:</span>{' '}
                                      <Badge 
                                        variant={deviceStatusInfo.subscription_active ? 'success' : 'warning'}
                                        size="sm"
                                      >
                                        {deviceStatusInfo.subscription_active ? '✓ Активна' : '✗ Неактивна'}
                                      </Badge>
                                    </div>
                                  )}
                                </div>
                              </div>
                              <div className="flex flex-col gap-2 ml-4">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    startEditing(device);
                                  }}
                                >
                                  Редактировать
                                </Button>
                                {isSelected && (
                                  <Button
                                    variant="info"
                                    size="sm"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      checkStatus();
                                    }}
                                  >
                                    Проверить
                                  </Button>
                                )}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      ) : null}

      {/* Детальная информация о выбранном устройстве */}
      {selectedDevice ? (
        <Card className="mb-6">
          <div>
            <h3 className="text-lg leading-6 font-semibold text-gray-900 mb-4 tracking-tight">
              {selectedDevice.name}
            </h3>
            
            <dl className="grid grid-cols-1 gap-x-4 gap-y-4 sm:grid-cols-2">
              <div>
                <dt className="text-sm font-medium text-gray-500">IP адрес</dt>
                <dd className="mt-1 text-sm text-gray-900">{selectedDevice.ip_address}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Пользователь</dt>
                <dd className="mt-1 text-sm text-gray-900">{selectedDevice.username}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Тип терминала</dt>
                <dd className="mt-1">
                  <Badge variant="info">
                    {selectedDevice.device_type === 'entry' ? '🚪 Вход' :
                     selectedDevice.device_type === 'exit' ? '🚶 Выход' :
                     selectedDevice.device_type === 'both' ? '🔄 Оба' :
                     '📍 Другое'}
                  </Badge>
                </dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Местоположение</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {selectedDevice.location || 'Не указано'}
                </dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Статус</dt>
                <dd className="mt-1">
                  <Badge variant={selectedDevice.is_active ? 'success' : 'error'}>
                    {selectedDevice.is_active ? 'Активно' : 'Неактивно'}
                  </Badge>
                </dd>
              </div>
              {devicesStatus && devicesStatus.length > 0 && (
                <div>
                  <dt className="text-sm font-medium text-gray-500">Подписка на события</dt>
                  <dd className="mt-1">
                    {(() => {
                      const status = devicesStatus.find(s => s.device_id === selectedDevice.id);
                      if (!status) return <Badge variant="secondary">Неизвестно</Badge>;
                      return (
                        <Badge variant={status.subscription_active ? 'success' : 'warning'}>
                          {status.subscription_active ? '✓ Активна' : '✗ Неактивна'}
                        </Badge>
                      );
                    })()}
                  </dd>
                </div>
              )}
              <div>
                <dt className="text-sm font-medium text-gray-500">Последняя синхронизация</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {selectedDevice.last_sync 
                    ? new Date(selectedDevice.last_sync).toLocaleString('ru-RU', {
                        timeZone: 'Asia/Baku',
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit'
                      })
                    : 'Никогда'}
                </dd>
              </div>
            </dl>

            {/* Проверка соединения */}
            <div className="mt-6 border-t pt-4">
              <div className="flex flex-wrap gap-2">
                <Button onClick={() => checkStatus()}>
                  Проверить соединение
                </Button>
                
                <Button 
                  variant="secondary" 
                  onClick={() => {
                    refetchStatuses();
                    showToast.info('Обновление статусов...');
                  }}
                >
                  Обновить статусы
                </Button>

                <Button 
                  variant="info" 
                  onClick={() => reconnectMutation.mutate(selectedDevice.id)}
                  disabled={reconnectMutation.isPending}
                  loading={reconnectMutation.isPending}
                >
                  Переподключить
                </Button>
                
                <Button variant="warning" onClick={() => startEditing(selectedDevice)}>
                  Редактировать
                </Button>

                {deviceStatus?.connected && supportedFeatures?.features?.system?.reboot && (
                  <Button
                    variant="error"
                    onClick={() => handleReboot(selectedDevice.id)}
                    disabled={rebootMutation.isPending}
                    loading={rebootMutation.isPending}
                  >
                    Перезагрузить устройство
                  </Button>
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
                        {system.reboot && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Перезагрузка</span>
                          </div>
                        )}
                        {system.factory_reset && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Сброс настроек</span>
                          </div>
                        )}
                        {system.firmware_update && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Обновление прошивки</span>
                          </div>
                        )}
                        {system.snapshot && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Снимок экрана</span>
                          </div>
                        )}
                        {system.preview && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Предпросмотр</span>
                          </div>
                        )}
                        {system.configuration_import && (
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
                        {network.wifi && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Wi-Fi</span>
                          </div>
                        )}
                        {network.https && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>HTTPS</span>
                          </div>
                        )}
                        {network.ssh && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>SSH</span>
                          </div>
                        )}
                        {network.websocket && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>WebSocket</span>
                          </div>
                        )}
                        {network.ezviz && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>EZVIZ</span>
                          </div>
                        )}
                        {network.ddns === false && (
                          <div className="flex items-center text-sm">
                            <span className="text-red-600 mr-2">✗</span>
                            <span className="text-gray-500">DDNS</span>
                          </div>
                        )}
                        {network.ftp === false && (
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
                        {security.user_check && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Проверка пользователей</span>
                          </div>
                        )}
                        {security.config_import && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Импорт конфигурации</span>
                          </div>
                        )}
                        {security.config_export && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Экспорт конфигурации</span>
                          </div>
                        )}
                        {security.certificates && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Сертификаты</span>
                          </div>
                        )}
                        {security.password_protection && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Защита паролем</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Контроль доступа */}
                    {access.supported && (
                      <div>
                        <h4 className="text-sm font-semibold text-gray-700 mb-2">Контроль доступа</h4>
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Access Control</span>
                          </div>
                          {access.encryption && (
                            <div className="flex items-center text-sm">
                              <span className="text-green-600 mr-2">✓</span>
                              <span>Шифрование</span>
                            </div>
                          )}
                          {access.acs_update && (
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
                        <div>Видео входов: —</div>
                        <div>Аудио входов: —</div>
                        <div>Аудио выходов: —</div>
                        <div>Голосовая связь: — канал</div>
                      </div>
                    </div>

                    {/* Дополнительно */}
                    <div>
                      <h4 className="text-sm font-semibold text-gray-700 mb-2">Дополнительно</h4>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                        {other.bluetooth && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Bluetooth</span>
                          </div>
                        )}
                        {other.manual_snapshot && (
                          <div className="flex items-center text-sm">
                            <span className="text-green-600 mr-2">✓</span>
                            <span>Ручной снимок</span>
                          </div>
                        )}
                        {other.user_manual_qr && (
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
        </Card>
      ) : (
        <Card className="mb-6">
          <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
            <p className="text-sm text-yellow-700">
              {devices && devices.length === 0 
                ? 'Устройство не настроено. Добавьте терминал для управления пользователями.'
                : 'Выберите терминал из списка выше для просмотра детальной информации.'}
            </p>
          </div>
        </Card>
      )}

      {/* Редактирование устройства */}
      {isEditingDevice && editingDeviceData && (
        <Card className="mb-6" title="Редактирование устройства">
          <form onSubmit={handleUpdateSubmit}>
            <div className="space-y-4">
              <Input
                label="Название"
                type="text"
                required
                value={editingDeviceData.name}
                onChange={(e) => setEditingDeviceData({...editingDeviceData, name: e.target.value})}
              />
              <Input
                label="IP адрес"
                type="text"
                required
                value={editingDeviceData.ip_address}
                onChange={(e) => setEditingDeviceData({...editingDeviceData, ip_address: e.target.value})}
              />
              <Input
                label="Имя пользователя"
                type="text"
                required
                value={editingDeviceData.username}
                onChange={(e) => setEditingDeviceData({...editingDeviceData, username: e.target.value})}
              />
              <Input
                label="Новый пароль (оставьте пустым, если не меняете)"
                type="password"
                autoComplete="new-password"
                value={editingDeviceData.password}
                onChange={(e) => setEditingDeviceData({...editingDeviceData, password: e.target.value})}
                placeholder="Оставьте пустым, чтобы сохранить текущий пароль"
              />

              {/* Новые поля */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Тип терминала
                </label>
                <select
                  value={editingDeviceData.device_type}
                  onChange={(e) => setEditingDeviceData({...editingDeviceData, device_type: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="entry">Вход</option>
                  <option value="exit">Выход</option>
                  <option value="both">Оба (вход и выход)</option>
                  <option value="other">Другое</option>
                </select>
              </div>

              <Input
                label="Местоположение (опционально)"
                type="text"
                value={editingDeviceData.location}
                onChange={(e) => setEditingDeviceData({...editingDeviceData, location: e.target.value})}
                placeholder="Например: Главный вход, 1 этаж"
              />
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <Button
                variant="secondary"
                type="button"
                onClick={() => {
                  setIsEditingDevice(false);
                  setEditingDeviceData(null);
                }}
              >
                Отмена
              </Button>
              <Button type="submit" loading={updateMutation.isPending}>
                Обновить
              </Button>
            </div>
          </form>
        </Card>
      )}


      {isAddingDevice && (
        <Card title="Новое устройство">
          <form onSubmit={handleSubmit}>
            <div className="space-y-4">
              <Input
                label="Название"
                type="text"
                required
                value={newDevice.name}
                onChange={(e) => setNewDevice({...newDevice, name: e.target.value})}
                placeholder="Например: Терминал Вход"
              />
              <Input
                label="IP адрес (в VPN сети)"
                type="text"
                required
                value={newDevice.ip_address}
                onChange={(e) => setNewDevice({...newDevice, ip_address: e.target.value})}
                placeholder="10.0.0.100"
              />
              <Input
                label="Имя пользователя"
                type="text"
                required
                value={newDevice.username}
                onChange={(e) => setNewDevice({...newDevice, username: e.target.value})}
              />
              <Input
                label="Пароль"
                type="password"
                autoComplete="new-password"
                required
                value={newDevice.password}
                onChange={(e) => setNewDevice({...newDevice, password: e.target.value})}
              />
              
              {/* Новые поля */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Тип терминала
                </label>
                <select
                  value={newDevice.device_type}
                  onChange={(e) => setNewDevice({...newDevice, device_type: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="entry">Вход</option>
                  <option value="exit">Выход</option>
                  <option value="both">Оба (вход и выход)</option>
                  <option value="other">Другое</option>
                </select>
              </div>

              <Input
                label="Местоположение (опционально)"
                type="text"
                value={newDevice.location}
                onChange={(e) => setNewDevice({...newDevice, location: e.target.value})}
                placeholder="Например: Главный вход, 1 этаж"
              />
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <Button
                variant="secondary"
                type="button"
                onClick={() => setIsAddingDevice(false)}
              >
                Отмена
              </Button>
              <Button type="submit" loading={createMutation.isPending}>
                Сохранить
              </Button>
            </div>
          </form>
        </Card>
      )}

      <ConfirmDialog
        isOpen={rebootConfirm}
        onClose={() => setRebootConfirm(false)}
        onConfirm={() => {
          if (selectedDeviceId) {
            rebootMutation.mutate(selectedDeviceId);
          }
          setRebootConfirm(false);
        }}
        title="Перезагрузка устройства"
        message="Вы уверены, что хотите перезагрузить устройство? Это может занять несколько минут."
        confirmText="Перезагрузить"
        cancelText="Отмена"
        variant="warning"
      />

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

