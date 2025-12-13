import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import Button from '../components/ui/Button';
import Modal from '../components/ui/Modal';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import Input from '../components/ui/Input';
import Badge from '../components/ui/Badge';
import Card from '../components/ui/Card';
import Skeleton from '../components/ui/Skeleton';
import showToast from '../utils/toast';

function UsersManagementPage() {
  const { isOperationsManager } = useAuth();
  const [activeTab, setActiveTab] = useState('terminal'); // 'terminal' или 'system'
  
  // Данные для пользователей терминала
  const [terminalUsers, setTerminalUsers] = useState([]);
  const [terminalLoading, setTerminalLoading] = useState(true);
  const [terminalError, setTerminalError] = useState('');
  const [showTerminalModal, setShowTerminalModal] = useState(false);
  const [editingTerminalUser, setEditingTerminalUser] = useState(null);
  const [roles, setRoles] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');

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

  useEffect(() => {
    if (isOperationsManager()) {
      fetchTerminalUsers();
      fetchSystemUsers();
      fetchRoles();
    }
  }, [isOperationsManager]);

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

  // Обработчики для пользователей терминала
  const handleTerminalSubmit = async (e) => {
    e.preventDefault();
    setTerminalError('');

    try {
      await axios.put(`/api/users/${editingTerminalUser.id}`, {
        role: terminalFormData.role,
      });
      
      setShowTerminalModal(false);
      setEditingTerminalUser(null);
      resetTerminalForm();
      showToast.success('Роль пользователя успешно обновлена');
      fetchTerminalUsers();
    } catch (error) {
      const errorMsg = error.response?.data?.detail || 'Ошибка сохранения';
      showToast.error(errorMsg);
      setTerminalError(errorMsg);
    }
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
  const handleSystemSubmit = async (e) => {
    e.preventDefault();
    setSystemError('');

    try {
      if (editingSystemUser) {
        // Обновление
        const updateData = { ...systemFormData };
        if (!updateData.password) {
          delete updateData.password;
        }
        await axios.put(`/api/system-users/${editingSystemUser.id}`, updateData);
      }
      
      setShowSystemModal(false);
      setEditingSystemUser(null);
      resetSystemForm();
      showToast.success(editingSystemUser ? 'Пользователь успешно обновлен' : 'Пользователь успешно создан');
      fetchSystemUsers();
    } catch (error) {
      const errorMsg = error.response?.data?.detail || 'Ошибка сохранения';
      showToast.error(errorMsg);
      setSystemError(errorMsg);
    }
  };

  const [systemDeleteConfirm, setSystemDeleteConfirm] = useState(null);

  const handleSystemDelete = async (userId) => {
    setSystemDeleteConfirm(userId);
  };

  const confirmSystemDelete = async () => {
    if (!systemDeleteConfirm) return;
    
    try {
      await axios.delete(`/api/system-users/${systemDeleteConfirm}`);
      showToast.success('Пользователь успешно удален');
      fetchSystemUsers();
      setSystemDeleteConfirm(null);
    } catch (error) {
      showToast.error(error.response?.data?.detail || 'Ошибка удаления');
      setSystemError(error.response?.data?.detail || 'Ошибка удаления');
    }
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

  const filteredTerminalUsers = terminalUsers.filter((user) => {
    const searchLower = searchTerm.toLowerCase();
    return (
      user.full_name?.toLowerCase().includes(searchLower) ||
      user.hikvision_id?.toLowerCase().includes(searchLower) ||
      user.department?.toLowerCase().includes(searchLower)
    );
  });

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
              onClick={() => setActiveTab('terminal')}
              className={`${
                activeTab === 'terminal'
                  ? 'border-[rgb(19,91,147)] text-[rgb(19,91,147)]'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
            >
              Роли пользователей терминала
            </button>
            <button
              onClick={() => setActiveTab('system')}
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

          {terminalLoading ? (
            <div className="p-6">Загрузка...</div>
          ) : (
            <div className="bg-white shadow overflow-hidden sm:rounded-md">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
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
                      <td colSpan="6" className="px-6 py-4 text-center text-gray-500">
                        {searchTerm ? 'Пользователи не найдены' : 'Нет пользователей'}
                      </td>
                    </tr>
                  ) : (
                    filteredTerminalUsers.map((user) => (
                      <tr key={user.id}>
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
                          <button
                            onClick={() => handleTerminalEdit(user)}
                            className="text-[rgb(19,91,147)] hover:text-[rgb(15,73,118)]"
                          >
                            Изменить роль
                          </button>
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
                        className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-[rgb(19,91,147)] text-base font-medium text-white hover:bg-[rgb(30,120,180)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[rgb(19,91,147)] sm:ml-3 sm:w-auto sm:text-sm"
                      >
                        Сохранить
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
                        className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-[rgb(19,91,147)] text-base font-medium text-white hover:bg-[rgb(30,120,180)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[rgb(19,91,147)] sm:ml-3 sm:w-auto sm:text-sm"
                      >
                        Сохранить
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
    </div>
  );
}

export default UsersManagementPage;

