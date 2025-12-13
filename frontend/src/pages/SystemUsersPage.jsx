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

function SystemUsersPage() {
  const { user, isOperationsManager } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [roles, setRoles] = useState([]);

  const [formData, setFormData] = useState({
    username: '',
    email: '',
    full_name: '',
    password: '',
    role: 'cleaner',
    is_active: true,
  });

  useEffect(() => {
    if (isOperationsManager()) {
      fetchUsers();
      fetchRoles();
    }
  }, [isOperationsManager]);

  const fetchUsers = async () => {
    try {
      const response = await axios.get('/api/system-users/');
      setUsers(response.data);
    } catch (error) {
      setError('Ошибка загрузки пользователей');
      console.error(error);
    } finally {
      setLoading(false);
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

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    try {
      if (editingUser) {
        // Обновление
        const updateData = { ...formData };
        if (!updateData.password) {
          delete updateData.password;
        }
        await axios.put(`/api/system-users/${editingUser.id}`, updateData);
      } else {
        // Создание
        await axios.post('/api/system-users/', formData);
      }
      
      setShowModal(false);
      setEditingUser(null);
      resetForm();
      showToast.success(editingUser ? 'Пользователь успешно обновлен' : 'Пользователь успешно создан');
      fetchUsers();
    } catch (error) {
      const errorMsg = error.response?.data?.detail || 'Ошибка сохранения';
      showToast.error(errorMsg);
      setError(errorMsg);
    }
  };

  const [deleteConfirm, setDeleteConfirm] = useState(null);

  const handleDelete = async (userId) => {
    setDeleteConfirm(userId);
  };

  const confirmDelete = async () => {
    if (!deleteConfirm) return;
    
    try {
      await axios.delete(`/api/system-users/${deleteConfirm}`);
      showToast.success('Пользователь успешно удален');
      fetchUsers();
      setDeleteConfirm(null);
    } catch (error) {
      showToast.error(error.response?.data?.detail || 'Ошибка удаления');
      setError(error.response?.data?.detail || 'Ошибка удаления');
    }
  };

  const handleEdit = (user) => {
    setEditingUser(user);
    setFormData({
      username: user.username,
      email: user.email || '',
      full_name: user.full_name || '',
      password: '',
      role: user.role,
      is_active: user.is_active,
    });
    setShowModal(true);
  };

  const resetForm = () => {
    setFormData({
      username: '',
      email: '',
      full_name: '',
      password: '',
      role: 'cleaner',
      is_active: true,
    });
    setEditingUser(null);
  };

  const getRoleDisplayName = (roleValue) => {
    const role = roles.find((r) => r.value === roleValue);
    return role ? role.display_name : roleValue;
  };

  if (!isOperationsManager()) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <p className="text-red-800">У вас нет доступа к этой странице. Требуется роль Operations Manager.</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Card>
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Управление пользователями системы</h1>
          <p className="mt-1 text-sm text-gray-500">
            Создание и управление пользователями для доступа к веб-интерфейсу
          </p>
        </div>
        <Button
          onClick={() => {
            resetForm();
            setShowModal(true);
          }}
        >
          Добавить пользователя
        </Button>
      </div>

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 rounded-md p-4">
          <p className="text-red-800">{error}</p>
        </div>
      )}

      <Card>
        {/* Desktop table view */}
        <div className="hidden lg:block overflow-x-auto">
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
            {users.map((user) => (
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
                  <Badge variant={user.is_active ? 'success' : 'error'}>
                    {user.is_active ? 'Активен' : 'Неактивен'}
                  </Badge>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                  <div className="flex items-center gap-2">
                    <Button variant="ghost" size="sm" onClick={() => handleEdit(user)}>
                      Редактировать
                    </Button>
                    <Button variant="error" size="sm" onClick={() => handleDelete(user.id)}>
                      Удалить
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>

        {/* Mobile card view */}
        <div className="lg:hidden space-y-3">
          {users.map((user) => (
            <div key={user.id} className="bg-white border border-gray-200 rounded-lg p-4 shadow-soft hover:shadow-medium transition-shadow duration-150">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold text-gray-900">{user.username}</p>
                  <Badge variant={user.is_active ? 'success' : 'error'}>
                    {user.is_active ? 'Активен' : 'Неактивен'}
                  </Badge>
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
                  <Button variant="ghost" size="sm" onClick={() => handleEdit(user)}>
                    Редактировать
                  </Button>
                  <Button variant="error" size="sm" onClick={() => handleDelete(user.id)}>
                    Удалить
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Modal */}
      <Modal
        isOpen={showModal}
        onClose={() => {
          setShowModal(false);
          resetForm();
        }}
        title={editingUser ? 'Редактировать пользователя' : 'Добавить пользователя'}
        footer={
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              onClick={() => {
                setShowModal(false);
                resetForm();
              }}
            >
              Отмена
            </Button>
            <Button onClick={handleSubmit}>
              {editingUser ? 'Сохранить' : 'Создать'}
            </Button>
          </div>
        }
      >
        <form onSubmit={handleSubmit}>
          <div className="space-y-4">
            <Input
              label="Имя пользователя"
              type="text"
              required
              disabled={!!editingUser}
              value={formData.username}
              onChange={(e) => setFormData({ ...formData, username: e.target.value })}
            />

            <Input
              label="Email"
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            />

            <Input
              label="Полное имя"
              type="text"
              value={formData.full_name}
              onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
            />

            <Input
              label={`Пароль ${editingUser ? '(оставьте пустым, чтобы не менять)' : ''}`}
              type="password"
              required={!editingUser}
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
            />

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Роль</label>
              <select
                value={formData.role}
                onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                className="block w-full rounded-md border-gray-300 shadow-sm focus:border-[rgb(19,91,147)] focus:ring-[rgb(19,91,147)] sm:text-sm"
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
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  className="rounded border-gray-300 text-[rgb(19,91,147)] focus:ring-[rgb(19,91,147)]"
                />
                <span className="ml-2 text-sm text-gray-700">Активен</span>
              </label>
            </div>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        isOpen={!!deleteConfirm}
        onClose={() => setDeleteConfirm(null)}
        onConfirm={confirmDelete}
        title="Удаление пользователя"
        message="Вы уверены, что хотите удалить этого пользователя?"
        confirmText="Удалить"
        cancelText="Отмена"
        variant="error"
      />
    </div>
  );
}

export default SystemUsersPage;

