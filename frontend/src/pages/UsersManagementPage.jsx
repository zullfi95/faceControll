import React, { useState, useEffect, useMemo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import Button from '../components/ui/Button';
import Modal from '../components/ui/Modal';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import Card from '../components/ui/Card';
import showToast from '../utils/toast';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

function UsersManagementPage() {
  const { isOperationsManager } = useAuth();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState('terminal'); // 'terminal' или 'system'
  
  // Данные для пользователей терминала
  const [terminalUsers, setTerminalUsers] = useState([]);
  const [terminalLoading, setTerminalLoading] = useState(true);
  const [terminalError, setTerminalError] = useState('');
  const [showTerminalModal, setShowTerminalModal] = useState(false);
  const [editingTerminalUser, setEditingTerminalUser] = useState(null);
  const [roles, setRoles] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');

  // Состояния для статистики
  const [statisticsUser, setStatisticsUser] = useState(null);
  const [userStatistics, setUserStatistics] = useState(null);
  const [isLoadingStatistics, setIsLoadingStatistics] = useState(false);

  // Состояния для привязки к смене
  const [showShiftAssignmentModal, setShowShiftAssignmentModal] = useState(false);
  const [selectedUserForShift, setSelectedUserForShift] = useState(null);
  const [selectedShiftId, setSelectedShiftId] = useState('');
  const [shiftStartDate, setShiftStartDate] = useState('');
  const [shiftEndDate, setShiftEndDate] = useState('');

  // Данные для системных пользователей
  const [systemUsers, setSystemUsers] = useState([]);
  const [systemLoading, setSystemLoading] = useState(true);
  const [systemError, setSystemError] = useState('');
  const [showSystemModal, setShowSystemModal] = useState(false);
  const [editingSystemUser, setEditingSystemUser] = useState(null);

  const [terminalFormData, setTerminalFormData] = useState({
    role: 'cleaner',
  });

  const [systemFormData, setSystemFormData] = useState({
    username: '',
    email: '',
    full_name: '',
    password: '',
    role: 'cleaner',
    is_active: true,
  });

  // Состояния для выбора пользователей терминала
  const [selectedUserIds, setSelectedUserIds] = useState(new Set());

  // Состояния для массовых операций
  const [showBulkRoleModal, setShowBulkRoleModal] = useState(false);
  const [showBulkShiftModal, setShowBulkShiftModal] = useState(false);

  // Загрузка списка смен
  const { data: workShifts = [], isLoading: isLoadingShifts } = useQuery({
    queryKey: ['work-shifts'],
    queryFn: async () => {
      const res = await axios.get('/api/work-shifts/?active_only=true');
      return res.data;
    },
    enabled: isOperationsManager(),
  });

  useEffect(() => {
    if (isOperationsManager()) {
      fetchTerminalUsers();
      fetchSystemUsers();
      fetchRoles();
    }
  }, [isOperationsManager]); // isOperationsManager стабильная функция из контекста

  const fetchTerminalUsers = async () => {
    try {
      const response = await axios.get('/api/users/');
      setTerminalUsers(response.data);
    } catch (error) {
      setTerminalError('Ошибка загрузки пользователей');
      console.error(error);
    } finally {
      setTerminalLoading(false);
    }
  };

  const fetchSystemUsers = async () => {
    try {
      const response = await axios.get('/api/system-users/');
      setSystemUsers(response.data);
    } catch (error) {
      setSystemError('Ошибка загрузки пользователей');
      console.error(error);
    } finally {
      setSystemLoading(false);
    }
  };

  const fetchRoles = async () => {
    try {
      const response = await axios.get('/api/roles');
      setRoles(response.data.roles);
    } catch (error) {
      console.error('Failed to fetch roles:', error);
    }
  };

  // Функции управления выбором пользователей терминала
  const handleSelectUser = (userId) => {
    const newSelected = new Set(selectedUserIds);
    if (newSelected.has(userId)) {
      newSelected.delete(userId);
    } else {
      newSelected.add(userId);
    }
    setSelectedUserIds(newSelected);
  };

  const handleSelectAll = () => {
    const allUserIds = new Set(filteredTerminalUsers.map(user => user.id));
    setSelectedUserIds(allUserIds);
  };

  const handleDeselectAll = () => {
    setSelectedUserIds(new Set());
  };

  // Мутации для операций с пользователями терминала
  const updateTerminalUserRoleMutation = useMutation({
    mutationFn: async ({ userId, role }) => {
      return axios.put(`/api/users/${userId}`, { role });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['terminal-users'] });
      setShowTerminalModal(false);
      setEditingTerminalUser(null);
      resetTerminalForm();
      showToast.success('Роль пользователя успешно обновлена');
    },
    onError: (error) => {
      const errorMsg = error.response?.data?.detail || 'Ошибка сохранения';
      showToast.error(errorMsg);
      setTerminalError(errorMsg);
    }
  });

  const bulkUpdateRoleMutation = useMutation({
    mutationFn: async ({ userIds, role }) => {
      const results = await Promise.allSettled(
        userIds.map(userId => axios.put(`/api/users/${userId}`, { role }))
      );
      return results;
    },
    onSuccess: (results) => {
      const fulfilled = results.filter(result => result.status === 'fulfilled').length;
      const rejected = results.filter(result => result.status === 'rejected').length;

      queryClient.invalidateQueries({ queryKey: ['terminal-users'] });

      if (rejected === 0) {
        showToast.success(`Роль успешно изменена для всех ${fulfilled} пользователей`);
      } else {
        showToast.warning(`Роль изменена для ${fulfilled} пользователей. Ошибок: ${rejected}`);
      }

      setShowBulkRoleModal(false);
      setSelectedUserIds(new Set());
    },
    onError: (error) => {
      showToast.error('Произошла ошибка при выполнении массовой операции');
    }
  });

  const bulkAssignToShiftMutation = useMutation({
    mutationFn: async ({ userIds, shiftId, startDate, endDate }) => {
      const results = await Promise.allSettled(
        userIds.map(userId =>
          axios.post('/api/user-shift-assignments/', {
            user_id: userId,
            shift_id: parseInt(shiftId),
            start_date: startDate || null,
            end_date: endDate || null,
            is_active: true,
          })
        )
      );
      return results;
    },
    onSuccess: (results) => {
      const fulfilled = results.filter(result => result.status === 'fulfilled').length;
      const rejected = results.filter(result => result.status === 'rejected').length;

      queryClient.invalidateQueries({ queryKey: ['terminal-users'] });

      if (rejected === 0) {
        showToast.success(`Пользователи успешно привязаны к смене (${fulfilled})`);
      } else {
        showToast.warning(`Привязано к смене: ${fulfilled}. Ошибок: ${rejected}`);
      }

      setShowBulkShiftModal(false);
      setSelectedUserIds(new Set());
      setSelectedShiftId('');
      setShiftStartDate('');
      setShiftEndDate('');
    },
    onError: (error) => {
      showToast.error('Произошла ошибка при привязке к смене');
    }
  });

  // Мутации для системных пользователей
  const updateSystemUserMutation = useMutation({
    mutationFn: async ({ userId, data }) => {
      const updateData = { ...data };
      if (!updateData.password) {
        delete updateData.password;
      }
      return axios.put(`/api/system-users/${userId}`, updateData);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['system-users'] });
      setShowSystemModal(false);
      setEditingSystemUser(null);
      resetSystemForm();
      showToast.success('Пользователь успешно обновлен');
    },
    onError: (error) => {
      const errorMsg = error.response?.data?.detail || 'Ошибка сохранения';
      showToast.error(errorMsg);
      setSystemError(errorMsg);
    }
  });

  const deleteSystemUserMutation = useMutation({
    mutationFn: (userId) => axios.delete(`/api/system-users/${userId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['system-users'] });
      showToast.success('Пользователь успешно удален');
      setSystemDeleteConfirm(null);
    },
    onError: (error) => {
      const errorMsg = error.response?.data?.detail || 'Ошибка удаления';
      showToast.error(errorMsg);
      setSystemError(errorMsg);
    }
  });

  // Обработчики для пользователей терминала
  const handleTerminalSubmit = (e) => {
    e.preventDefault();
    setTerminalError('');

    updateTerminalUserRoleMutation.mutate({
      userId: editingTerminalUser.id,
      role: terminalFormData.role
    });
  };

  const handleTerminalEdit = (user) => {
    setEditingTerminalUser(user);
    setTerminalFormData({
      role: user.role || 'cleaner',
    });
    setShowTerminalModal(true);
  };

  const resetTerminalForm = () => {
    setTerminalFormData({
      role: 'cleaner',
    });
    setEditingTerminalUser(null);
  };

  // Обработчики для системных пользователей
  const handleSystemSubmit = (e) => {
    e.preventDefault();
    setSystemError('');

    updateSystemUserMutation.mutate({
      userId: editingSystemUser.id,
      data: systemFormData
    });
  };

  const [systemDeleteConfirm, setSystemDeleteConfirm] = useState(null);

  const handleSystemDelete = async (userId) => {
    setSystemDeleteConfirm(userId);
  };

  const confirmSystemDelete = () => {
    if (!systemDeleteConfirm) return;

    deleteSystemUserMutation.mutate(systemDeleteConfirm);
  };

  const handleSystemEdit = (user) => {
    setEditingSystemUser(user);
    setSystemFormData({
      username: user.username,
      email: user.email || '',
      full_name: user.full_name || '',
      password: '',
      role: user.role,
      is_active: user.is_active,
    });
    setShowSystemModal(true);
  };

  const resetSystemForm = () => {
    setSystemFormData({
      username: '',
      email: '',
      full_name: '',
      password: '',
      role: 'cleaner',
      is_active: true,
    });
    setEditingSystemUser(null);
  };

  const getRoleDisplayName = (roleValue) => {
    const role = roles.find((r) => r.value === roleValue);
    return role ? role.display_name : roleValue;
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

  // Обработка привязки к смене
  const handleAssignToShift = (user) => {
    setSelectedUserForShift(user);
    setSelectedShiftId('');
    setShiftStartDate('');
    setShiftEndDate('');
    setShowShiftAssignmentModal(true);
  };

  const handleShiftAssignmentSubmit = (e) => {
    e.preventDefault();
    if (!selectedShiftId || !selectedUserForShift) {
      showToast.error('Выберите смену');
      return;
    }

    // Используем bulkAssignToShiftMutation для одиночной операции
    bulkAssignToShiftMutation.mutate({
      userIds: [selectedUserForShift.id],
      shiftId: selectedShiftId,
      startDate: shiftStartDate,
      endDate: shiftEndDate
    });
  };

  const filteredTerminalUsers = useMemo(() => {
    const searchLower = searchTerm.toLowerCase();
    return terminalUsers.filter((user) =>
      user.full_name?.toLowerCase().includes(searchLower) ||
      user.hikvision_id?.toLowerCase().includes(searchLower) ||
      user.department?.toLowerCase().includes(searchLower)
    );
  }, [terminalUsers, searchTerm]);

  if (!isOperationsManager()) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <p className="text-red-800">У вас нет доступа к этой странице. Требуется роль Operations Manager.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-4">Управление пользователями и ролями</h1>
        
        {/* Табы */}
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => {
                setActiveTab('terminal');
                setSelectedUserIds(new Set()); // Очистить выбор при переключении
              }}
              className={`${
                activeTab === 'terminal'
                  ? 'border-[rgb(19,91,147)] text-[rgb(19,91,147)]'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
            >
              Роли пользователей терминала
            </button>
            <button
              onClick={() => {
                setActiveTab('system');
                setSelectedUserIds(new Set()); // Очистить выбор при переключении
              }}
              className={`${
                activeTab === 'system'
                  ? 'border-[rgb(19,91,147)] text-[rgb(19,91,147)]'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
            >
              Пользователи системы
            </button>
          </nav>
        </div>
      </div>

      {/* Вкладка: Роли пользователей терминала */}
      {activeTab === 'terminal' && (
        <>
          <div className="mb-4">
            <p className="text-gray-600 mb-4">
              Назначьте роли пользователям из терминала. Только Operations Manager может изменять роли.
            </p>
            
            {/* Поиск */}
            <div className="mb-4">
              <input
                type="text"
                placeholder="Поиск по имени, ID или отделу..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full max-w-md px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-[rgb(19,91,147)]"
              />
            </div>
          </div>

          {terminalError && (
            <div className="mb-4 bg-red-50 border border-red-200 rounded-md p-4">
              <p className="text-red-800">{terminalError}</p>
            </div>
          )}

          {/* Панель массовых действий */}
          {selectedUserIds.size > 0 && (
            <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-md">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span className="text-sm font-medium text-gray-900">
                    Выбрано пользователей: {selectedUserIds.size}
                  </span>
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => setShowBulkRoleModal(true)}
                    className="inline-flex items-center px-3 py-1.5 border border-transparent text-sm font-medium rounded-md text-white bg-[rgb(19,91,147)] hover:bg-[rgb(30,120,180)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[rgb(19,91,147)]"
                  >
                    Изменить роль
                  </button>
                  <button
                    onClick={() => setShowBulkShiftModal(true)}
                    className="inline-flex items-center px-3 py-1.5 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
                  >
                    Привязать к смене
                  </button>
                  <button
                    onClick={handleDeselectAll}
                    className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[rgb(19,91,147)]"
                  >
                    Снять выделение
                  </button>
                </div>
              </div>
            </div>
          )}

          {terminalLoading ? (
            <div className="p-6">Загрузка...</div>
          ) : (
            <div className="bg-white shadow overflow-hidden sm:rounded-md">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      <input
                        type="checkbox"
                        checked={selectedUserIds.size > 0 && selectedUserIds.size === filteredTerminalUsers.length}
                        onChange={() => {
                          if (selectedUserIds.size === filteredTerminalUsers.length) {
                            handleDeselectAll();
                          } else {
                            handleSelectAll();
                          }
                        }}
                        className="h-4 w-4 text-[rgb(19,91,147)] focus:ring-[rgb(19,91,147)] border-gray-300 rounded"
                      />
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      ID (Hikvision)
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Полное имя
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Отдел
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Текущая роль
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Статус
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Действия
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {filteredTerminalUsers.length === 0 ? (
                    <tr>
                      <td colSpan="7" className="px-6 py-4 text-center text-gray-500">
                        {searchTerm ? 'Пользователи не найдены' : 'Нет пользователей'}
                      </td>
                    </tr>
                  ) : (
                    filteredTerminalUsers.map((user) => (
                      <tr key={user.id}>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <input
                            type="checkbox"
                            checked={selectedUserIds.has(user.id)}
                            onChange={() => handleSelectUser(user.id)}
                            className="h-4 w-4 text-[rgb(19,91,147)] focus:ring-[rgb(19,91,147)] border-gray-300 rounded"
                          />
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                          {user.hikvision_id}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {user.full_name || '-'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {user.department || '-'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">
                            {getRoleDisplayName(user.role || 'cleaner')}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span
                            className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                              user.is_active
                                ? 'bg-green-100 text-green-800'
                                : 'bg-red-100 text-red-800'
                            }`}
                          >
                            {user.is_active ? 'Активен' : 'Неактивен'}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => handleTerminalEdit(user)}
                              className="text-[rgb(19,91,147)] hover:text-[rgb(15,73,118)]"
                            >
                              Изменить роль
                            </button>
                            <button
                              onClick={() => handleViewStatistics(user)}
                              className="text-blue-600 hover:text-blue-800"
                            >
                              Статистика
                            </button>
                            <button
                              onClick={() => handleAssignToShift(user)}
                              className="text-green-600 hover:text-green-800"
                            >
                              Привязать к смене
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* Modal для изменения роли пользователя терминала */}
          {showTerminalModal && (
            <div className="fixed z-10 inset-0 overflow-y-auto">
              <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
                <div
                  className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
                  onClick={() => {
                    setShowTerminalModal(false);
                    resetTerminalForm();
                  }}
                ></div>

                <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
                  <form onSubmit={handleTerminalSubmit}>
                    <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                      <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                        Изменить роль пользователя
                      </h3>

                      <div className="mb-4">
                        <p className="text-sm text-gray-600 mb-2">
                          <strong>Пользователь:</strong> {editingTerminalUser?.full_name || editingTerminalUser?.hikvision_id}
                        </p>
                        <p className="text-sm text-gray-600">
                          <strong>ID:</strong> {editingTerminalUser?.hikvision_id}
                        </p>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">Роль</label>
                        <select
                          value={terminalFormData.role}
                          onChange={(e) => setTerminalFormData({ ...terminalFormData, role: e.target.value })}
                          className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-[rgb(19,91,147)] focus:border-[rgb(19,91,147)]"
                          required
                        >
                          {roles.map((role) => (
                            <option key={role.value} value={role.value}>
                              {role.display_name}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>

                    <div className="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
                      <button
                        type="submit"
                        disabled={updateTerminalUserRoleMutation.isPending}
                        className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-[rgb(19,91,147)] text-base font-medium text-white hover:bg-[rgb(30,120,180)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[rgb(19,91,147)] disabled:opacity-50 disabled:cursor-not-allowed sm:ml-3 sm:w-auto sm:text-sm"
                      >
                        {updateTerminalUserRoleMutation.isPending ? 'Сохранение...' : 'Сохранить'}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setShowTerminalModal(false);
                          resetTerminalForm();
                        }}
                        className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[rgb(19,91,147)] sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm"
                      >
                        Отмена
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* Вкладка: Пользователи системы */}
      {activeTab === 'system' && (
        <>
          <div className="mb-6">
            <p className="text-gray-600 mb-4">
              Управление пользователями системы (для доступа к веб-интерфейсу). Создание новых пользователей доступно только на странице "Сотрудники".
            </p>
          </div>

          {systemError && (
            <div className="mb-4 bg-red-50 border border-red-200 rounded-md p-4">
              <p className="text-red-800">{systemError}</p>
            </div>
          )}

          {systemLoading ? (
            <div className="p-6">Загрузка...</div>
          ) : (
            <>
              {/* Desktop table view */}
              <div className="hidden lg:block bg-white shadow overflow-hidden sm:rounded-md">
                <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Имя пользователя
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Email
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Полное имя
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Роль
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Статус
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Действия
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {systemUsers.map((user) => (
                    <tr key={user.id}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {user.username}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {user.email || '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {user.full_name || '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {getRoleDisplayName(user.role)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span
                          className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                            user.is_active
                              ? 'bg-green-100 text-green-800'
                              : 'bg-red-100 text-red-800'
                          }`}
                        >
                          {user.is_active ? 'Активен' : 'Неактивен'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        <button
                          onClick={() => handleSystemEdit(user)}
                          className="text-[rgb(19,91,147)] hover:text-[rgb(30,120,180)] mr-4"
                        >
                          Редактировать
                        </button>
                        <Button
                          variant="error"
                          size="sm"
                          onClick={() => handleSystemDelete(user.id)}
                        >
                          Удалить
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile card view */}
            <div className="lg:hidden space-y-3">
              {systemUsers.map((user) => (
                <div key={user.id} className="bg-white border border-gray-200 rounded-lg p-4 shadow-soft hover:shadow-medium transition-shadow duration-150">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-semibold text-gray-900">{user.username}</p>
                      <span
                        className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                          user.is_active
                            ? 'bg-green-100 text-green-800'
                            : 'bg-red-100 text-red-800'
                        }`}
                      >
                        {user.is_active ? 'Активен' : 'Неактивен'}
                      </span>
                    </div>
                    <div className="space-y-1 text-xs">
                      <div>
                        <span className="text-gray-500">Email:</span>
                        <span className="ml-1 text-gray-700">{user.email || '-'}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Полное имя:</span>
                        <span className="ml-1 text-gray-700">{user.full_name || '-'}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Роль:</span>
                        <span className="ml-1 text-gray-700 font-medium">{getRoleDisplayName(user.role)}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 pt-2">
                      <button
                        onClick={() => handleSystemEdit(user)}
                        className="text-[rgb(19,91,147)] hover:text-[rgb(30,120,180)] text-sm font-medium"
                      >
                        Редактировать
                      </button>
                      <Button
                        variant="error"
                        size="sm"
                        onClick={() => handleSystemDelete(user.id)}
                      >
                        Удалить
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
          )}

          {/* Modal для редактирования системного пользователя */}
          {showSystemModal && (
            <div className="fixed z-10 inset-0 overflow-y-auto">
              <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
                <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={() => setShowSystemModal(false)}></div>

                <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
                  <form onSubmit={handleSystemSubmit}>
                    <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                      <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                        Редактировать пользователя
                      </h3>

                      <div className="space-y-4">
                        <div>
                          <label className="block text-sm font-medium text-gray-700">Имя пользователя</label>
                          <input
                            type="text"
                            required
                            disabled={!!editingSystemUser}
                            value={systemFormData.username}
                            onChange={(e) => setSystemFormData({ ...systemFormData, username: e.target.value })}
                            className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-[rgb(19,91,147)] focus:border-[rgb(19,91,147)]"
                          />
                        </div>

                        <div>
                          <label className="block text-sm font-medium text-gray-700">Email</label>
                          <input
                            type="email"
                            value={systemFormData.email}
                            onChange={(e) => setSystemFormData({ ...systemFormData, email: e.target.value })}
                            className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-[rgb(19,91,147)] focus:border-[rgb(19,91,147)]"
                          />
                        </div>

                        <div>
                          <label className="block text-sm font-medium text-gray-700">Полное имя</label>
                          <input
                            type="text"
                            value={systemFormData.full_name}
                            onChange={(e) => setSystemFormData({ ...systemFormData, full_name: e.target.value })}
                            className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-[rgb(19,91,147)] focus:border-[rgb(19,91,147)]"
                          />
                        </div>

                        <div>
                          <label className="block text-sm font-medium text-gray-700">
                            Пароль (оставьте пустым, чтобы не менять)
                          </label>
                          <input
                            type="password"
                            autoComplete="new-password"
                            value={systemFormData.password}
                            onChange={(e) => setSystemFormData({ ...systemFormData, password: e.target.value })}
                            className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-[rgb(19,91,147)] focus:border-[rgb(19,91,147)]"
                          />
                        </div>

                        <div>
                          <label className="block text-sm font-medium text-gray-700">Роль</label>
                          <select
                            value={systemFormData.role}
                            onChange={(e) => setSystemFormData({ ...systemFormData, role: e.target.value })}
                            className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-[rgb(19,91,147)] focus:border-[rgb(19,91,147)]"
                          >
                            {roles.map((role) => (
                              <option key={role.value} value={role.value}>
                                {role.display_name}
                              </option>
                            ))}
                          </select>
                        </div>

                        <div>
                          <label className="flex items-center">
                            <input
                              type="checkbox"
                              checked={systemFormData.is_active}
                              onChange={(e) => setSystemFormData({ ...systemFormData, is_active: e.target.checked })}
                              className="rounded border-gray-300 text-[rgb(19,91,147)] focus:ring-[rgb(19,91,147)]"
                            />
                            <span className="ml-2 text-sm text-gray-700">Активен</span>
                          </label>
                        </div>
                      </div>
                    </div>

                    <div className="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
                      <button
                        type="submit"
                        disabled={updateSystemUserMutation.isPending}
                        className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-[rgb(19,91,147)] text-base font-medium text-white hover:bg-[rgb(30,120,180)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[rgb(19,91,147)] disabled:opacity-50 disabled:cursor-not-allowed sm:ml-3 sm:w-auto sm:text-sm"
                      >
                        {updateSystemUserMutation.isPending ? 'Сохранение...' : 'Сохранить'}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setShowSystemModal(false);
                          resetSystemForm();
                        }}
                        className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[rgb(19,91,147)] sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm"
                      >
                        Отмена
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      <ConfirmDialog
        isOpen={!!systemDeleteConfirm}
        onClose={() => setSystemDeleteConfirm(null)}
        onConfirm={confirmSystemDelete}
        title="Удаление пользователя"
        message="Вы уверены, что хотите удалить этого пользователя?"
        confirmText="Удалить"
        cancelText="Отмена"
        variant="error"
      />

      {/* Модальное окно статистики пользователя */}
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

      {/* Модальное окно привязки к смене */}
      {showShiftAssignmentModal && (
        <div className="fixed z-10 inset-0 overflow-y-auto">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div
              className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
              onClick={() => {
                setShowShiftAssignmentModal(false);
                setSelectedUserForShift(null);
                setSelectedShiftId('');
                setShiftStartDate('');
                setShiftEndDate('');
              }}
            ></div>

            <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
              <form onSubmit={handleShiftAssignmentSubmit}>
                <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                  <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                    Привязать пользователя к смене
                  </h3>

                  <div className="mb-4">
                    <p className="text-sm text-gray-600 mb-2">
                      <strong>Пользователь:</strong> {selectedUserForShift?.full_name || selectedUserForShift?.hikvision_id}
                    </p>
                    <p className="text-sm text-gray-600">
                      <strong>ID:</strong> {selectedUserForShift?.hikvision_id}
                    </p>
                  </div>

                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">Смена *</label>
                      {isLoadingShifts ? (
                        <div className="text-sm text-gray-500">Загрузка смен...</div>
                      ) : (
                        <select
                          value={selectedShiftId}
                          onChange={(e) => setSelectedShiftId(e.target.value)}
                          className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-[rgb(19,91,147)] focus:border-[rgb(19,91,147)]"
                          required
                        >
                          <option value="">Выберите смену</option>
                          {workShifts.map((shift) => (
                            <option key={shift.id} value={shift.id}>
                              {shift.name} {shift.description ? `- ${shift.description}` : ''}
                            </option>
                          ))}
                        </select>
                      )}
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Дата начала (необязательно)
                      </label>
                      <input
                        type="date"
                        value={shiftStartDate}
                        onChange={(e) => setShiftStartDate(e.target.value)}
                        className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-[rgb(19,91,147)] focus:border-[rgb(19,91,147)]"
                      />
                      <p className="mt-1 text-xs text-gray-500">Если не указано, привязка действует с сегодняшнего дня</p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Дата окончания (необязательно)
                      </label>
                      <input
                        type="date"
                        value={shiftEndDate}
                        onChange={(e) => setShiftEndDate(e.target.value)}
                        className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-[rgb(19,91,147)] focus:border-[rgb(19,91,147)]"
                      />
                      <p className="mt-1 text-xs text-gray-500">Если не указано, привязка действует бессрочно</p>
                    </div>
                  </div>
                </div>

                <div className="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
                  <button
                    type="submit"
                    className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-[rgb(19,91,147)] text-base font-medium text-white hover:bg-[rgb(30,120,180)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[rgb(19,91,147)] sm:ml-3 sm:w-auto sm:text-sm"
                  >
                    Привязать
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowShiftAssignmentModal(false);
                      setSelectedUserForShift(null);
                      setSelectedShiftId('');
                      setShiftStartDate('');
                      setShiftEndDate('');
                    }}
                    className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[rgb(19,91,147)] sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm"
                  >
                    Отмена
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Модальное окно массового изменения роли */}
      {showBulkRoleModal && (
        <div className="fixed z-10 inset-0 overflow-y-auto">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div
              className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
              onClick={() => setShowBulkRoleModal(false)}
            ></div>

            <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
              <form onSubmit={(e) => {
                e.preventDefault();
                const role = e.target.role.value;
                bulkUpdateRoleMutation.mutate({
                  userIds: Array.from(selectedUserIds),
                  role
                });
              }}>
                <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                  <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                    Изменить роль для выбранных пользователей ({selectedUserIds.size})
                  </h3>

                  <div className="mb-4">
                    <div className="max-h-32 overflow-y-auto bg-gray-50 rounded p-2 mb-4">
                      <p className="text-sm font-medium text-gray-700 mb-2">Выбранные пользователи:</p>
                      <div className="space-y-1">
                        {Array.from(selectedUserIds).map(userId => {
                          const user = filteredTerminalUsers.find(u => u.id === userId);
                          return user ? (
                            <div key={userId} className="text-xs text-gray-600">
                              {user.full_name || user.hikvision_id}
                            </div>
                          ) : null;
                        })}
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">Новая роль</label>
                      <select
                        name="role"
                        className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-[rgb(19,91,147)] focus:border-[rgb(19,91,147)]"
                        required
                        defaultValue="cleaner"
                      >
                        {roles.map((role) => (
                          <option key={role.value} value={role.value}>
                            {role.display_name}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>

                <div className="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
                  <button
                    type="submit"
                    disabled={bulkUpdateRoleMutation.isPending}
                    className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-[rgb(19,91,147)] text-base font-medium text-white hover:bg-[rgb(30,120,180)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[rgb(19,91,147)] disabled:opacity-50 disabled:cursor-not-allowed sm:ml-3 sm:w-auto sm:text-sm"
                  >
                    {bulkUpdateRoleMutation.isPending ? 'Применение...' : 'Применить'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowBulkRoleModal(false)}
                    className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[rgb(19,91,147)] sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm"
                  >
                    Отмена
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Модальное окно массовой привязки к смене */}
      {showBulkShiftModal && (
        <div className="fixed z-10 inset-0 overflow-y-auto">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div
              className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
              onClick={() => setShowBulkShiftModal(false)}
            ></div>

            <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
              <form onSubmit={(e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const shiftId = formData.get('shiftId');
                const startDate = formData.get('startDate') || null;
                const endDate = formData.get('endDate') || null;

                bulkAssignToShiftMutation.mutate({
                  userIds: Array.from(selectedUserIds),
                  shiftId,
                  startDate,
                  endDate
                });
              }}>
                <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                  <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                    Привязать выбранных пользователей к смене ({selectedUserIds.size})
                  </h3>

                  <div className="mb-4">
                    <div className="max-h-32 overflow-y-auto bg-gray-50 rounded p-2 mb-4">
                      <p className="text-sm font-medium text-gray-700 mb-2">Выбранные пользователи:</p>
                      <div className="space-y-1">
                        {Array.from(selectedUserIds).map(userId => {
                          const user = filteredTerminalUsers.find(u => u.id === userId);
                          return user ? (
                            <div key={userId} className="text-xs text-gray-600">
                              {user.full_name || user.hikvision_id}
                            </div>
                          ) : null;
                        })}
                      </div>
                    </div>

                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">Смена *</label>
                        {isLoadingShifts ? (
                          <div className="text-sm text-gray-500">Загрузка смен...</div>
                        ) : (
                          <select
                            name="shiftId"
                            className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-[rgb(19,91,147)] focus:border-[rgb(19,91,147)]"
                            required
                          >
                            <option value="">Выберите смену</option>
                            {workShifts.map((shift) => (
                              <option key={shift.id} value={shift.id}>
                                {shift.name} {shift.description ? `- ${shift.description}` : ''}
                              </option>
                            ))}
                          </select>
                        )}
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Дата начала (необязательно)
                        </label>
                        <input
                          name="startDate"
                          type="date"
                          className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-[rgb(19,91,147)] focus:border-[rgb(19,91,147)]"
                        />
                        <p className="mt-1 text-xs text-gray-500">Если не указано, привязка действует с сегодняшнего дня</p>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Дата окончания (необязательно)
                        </label>
                        <input
                          name="endDate"
                          type="date"
                          className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-[rgb(19,91,147)] focus:border-[rgb(19,91,147)]"
                        />
                        <p className="mt-1 text-xs text-gray-500">Если не указано, привязка действует бессрочно</p>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
                  <button
                    type="submit"
                    disabled={bulkAssignToShiftMutation.isPending}
                    className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-green-600 text-base font-medium text-white hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed sm:ml-3 sm:w-auto sm:text-sm"
                  >
                    {bulkAssignToShiftMutation.isPending ? 'Привязка...' : 'Привязать'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowBulkShiftModal(false)}
                    className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[rgb(19,91,147)] sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm"
                  >
                    Отмена
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default UsersManagementPage;

