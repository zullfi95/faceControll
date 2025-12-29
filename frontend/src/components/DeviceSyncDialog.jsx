import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import Modal from './ui/Modal';
import Button from './ui/Button';
import Badge from './ui/Badge';
import showToast from '../utils/toast';

/**
 * Диалог для синхронизации пользователя с несколькими терминалами
 */
const DeviceSyncDialog = ({ userId, userName, isOpen, onClose }) => {
  const queryClient = useQueryClient();
  const [selectedDevices, setSelectedDevices] = useState([]);

  // Получение групп устройств
  const { data: deviceGroups, isLoading: groupsLoading } = useQuery({
    queryKey: ['device-groups'],
    queryFn: async () => {
      const res = await axios.get('/api/devices/groups');
      return res.data;
    },
    enabled: isOpen
  });

  // Получение статуса синхронизации пользователя
  const { data: syncStatus, isLoading: statusLoading } = useQuery({
    queryKey: ['user-device-sync-status', userId],
    queryFn: async () => {
      const res = await axios.get(`/api/users/${userId}/device-sync-status`);
      return res.data;
    },
    enabled: isOpen && !!userId
  });

  // Mutation для синхронизации на несколько устройств
  const syncMutation = useMutation({
    mutationFn: ({ deviceIds, force }) =>
      axios.post(`/api/users/${userId}/sync-to-devices`, {
        device_ids: deviceIds,
        force: force
      }),
    onSuccess: (response) => {
      const { synced_count, failed_count } = response.data;
      
      if (failed_count === 0) {
        showToast.success(`✓ Успешно синхронизировано на ${synced_count} терминал(ов)!`);
      } else {
        showToast.warning(
          `Частичная синхронизация: ${synced_count} успешно, ${failed_count} ошибок`
        );
      }
      
      // Обновляем кеш
      queryClient.invalidateQueries(['users']);
      queryClient.invalidateQueries(['user-device-sync-status', userId]);
      
      // Закрываем диалог при полном успехе
      if (failed_count === 0) {
        onClose();
      }
    },
    onError: (error) => {
      showToast.error('Ошибка синхронизации: ' + (error.response?.data?.detail || error.message));
    }
  });

  // Переключение выбора устройства
  const toggleDevice = (deviceId) => {
    setSelectedDevices(prev =>
      prev.includes(deviceId)
        ? prev.filter(id => id !== deviceId)
        : [...prev, deviceId]
    );
  };

  // Синхронизация на выбранные устройства
  const handleSync = () => {
    if (selectedDevices.length === 0) {
      showToast.warning('Выберите хотя бы одно устройство');
      return;
    }
    
    syncMutation.mutate({
      deviceIds: selectedDevices,
      force: false
    });
  };

  // Синхронизация на все устройства
  const handleSyncAll = () => {
    if (!deviceGroups) return;
    
    const allDevices = [
      ...deviceGroups.entry,
      ...deviceGroups.exit,
      ...deviceGroups.both,
      ...deviceGroups.other
    ];
    
    const activeDeviceIds = allDevices
      .filter(d => d.is_active)
      .map(d => d.id);
    
    if (activeDeviceIds.length === 0) {
      showToast.warning('Нет активных устройств');
      return;
    }
    
    syncMutation.mutate({
      deviceIds: activeDeviceIds,
      force: false
    });
  };

  // Проверка, синхронизировано ли устройство
  const isSynced = (deviceId) => {
    if (!syncStatus || !syncStatus.synced_devices) return false;
    return syncStatus.synced_devices.some(
      s => s.device_id === deviceId && s.sync_status === 'synced'
    );
  };

  // Получение статуса синхронизации для устройства
  const getSyncStatus = (deviceId) => {
    if (!syncStatus || !syncStatus.synced_devices) return null;
    return syncStatus.synced_devices.find(s => s.device_id === deviceId);
  };

  // Рендер группы устройств
  const renderDeviceGroup = (title, devices, icon) => {
    if (!devices || devices.length === 0) return null;

    return (
      <div className="border rounded-lg p-4 bg-gray-50">
        <h4 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <span>{icon}</span>
          <span>{title}</span>
          <span className="text-sm font-normal text-gray-500">({devices.length})</span>
        </h4>
        
        <div className="space-y-2">
          {devices.map(device => {
            const syncInfo = getSyncStatus(device.id);
            const synced = isSynced(device.id);
            
            return (
              <div
                key={device.id}
                className="flex items-center justify-between py-2 px-3 bg-white rounded border hover:border-blue-300 transition-colors"
              >
                <label className="flex items-center gap-3 cursor-pointer flex-1">
                  <input
                    type="checkbox"
                    checked={selectedDevices.includes(device.id)}
                    onChange={() => toggleDevice(device.id)}
                    disabled={!device.is_active}
                    className="w-4 h-4 text-blue-600 rounded focus:ring-2 focus:ring-blue-500"
                  />
                  
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900">{device.name}</span>
                      {!device.is_active && (
                        <Badge variant="error" size="sm">Неактивен</Badge>
                      )}
                    </div>
                    {device.location && (
                      <span className="text-sm text-gray-500">{device.location}</span>
                    )}
                  </div>
                </label>
                
                {/* Статус синхронизации */}
                <div className="flex items-center gap-2">
                  {synced ? (
                    <Badge variant="success" size="sm">✓ Синхронизирован</Badge>
                  ) : syncInfo && syncInfo.sync_status === 'pending' ? (
                    <Badge variant="warning" size="sm">⏳ Ожидает</Badge>
                  ) : syncInfo && syncInfo.sync_status === 'failed' ? (
                    <Badge variant="error" size="sm">✗ Ошибка</Badge>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  if (!isOpen) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Синхронизация пользователя на терминалы`}
      size="large"
    >
      <div className="space-y-4">
        {/* Информация о пользователе */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <p className="text-sm text-blue-900">
            <span className="font-semibold">Пользователь:</span> {userName}
          </p>
          {syncStatus && (
            <p className="text-sm text-blue-700 mt-1">
              Синхронизировано: {syncStatus.total_synced} из {syncStatus.total_devices} терминалов
            </p>
          )}
        </div>

        {/* Быстрая синхронизация */}
        <div className="flex gap-2">
          <Button
            onClick={handleSyncAll}
            variant="primary"
            fullWidth
            disabled={syncMutation.isPending}
            loading={syncMutation.isPending}
          >
            🚀 Синхронизировать на все терминалы
          </Button>
        </div>

        <div className="text-sm text-gray-500 text-center">
          или выберите конкретные терминалы:
        </div>

        {/* Загрузка */}
        {(groupsLoading || statusLoading) && (
          <div className="text-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
            <p className="text-sm text-gray-500 mt-2">Загрузка...</p>
          </div>
        )}

        {/* Группы устройств */}
        {deviceGroups && !groupsLoading && (
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {renderDeviceGroup('Терминалы Входа', deviceGroups.entry, '🚪')}
            {renderDeviceGroup('Терминалы Выхода', deviceGroups.exit, '🚶')}
            {renderDeviceGroup('Универсальные', deviceGroups.both, '🔄')}
            {renderDeviceGroup('Другие', deviceGroups.other, '📍')}
          </div>
        )}

        {/* Кнопки действий */}
        <div className="flex justify-end gap-2 pt-4 border-t">
          <Button
            variant="secondary"
            onClick={onClose}
            disabled={syncMutation.isPending}
          >
            Отмена
          </Button>
          <Button
            onClick={handleSync}
            disabled={selectedDevices.length === 0 || syncMutation.isPending}
            loading={syncMutation.isPending}
          >
            Синхронизировать выбранные ({selectedDevices.length})
          </Button>
        </div>
      </div>
    </Modal>
  );
};

export default DeviceSyncDialog;

