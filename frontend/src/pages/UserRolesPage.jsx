import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import Button from '../components/ui/Button';
import Modal from '../components/ui/Modal';
import Input from '../components/ui/Input';
import Badge from '../components/ui/Badge';
import Card from '../components/ui/Card';
import Skeleton from '../components/ui/Skeleton';
import showToast from '../utils/toast';

function UserRolesPage() {
  const { isOperationsManager } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [roles, setRoles] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');

  const [formData, setFormData] = useState({
    role: 'cleaner',
  });

  useEffect(() => {
    if (isOperationsManager()) {
      fetchUsers();
      fetchRoles();
    }
  }, [isOperationsManager]);

  const fetchUsers = async () => {
    try {
      const response = await axios.get('/api/users/');
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
      await axios.put(`/api/users/${editingUser.id}`, {
        role: formData.role,
      });
      
      setShowModal(false);
      setEditingUser(null);
      resetForm();
      showToast.success('Роль пользователя успешно обновлена');
      fetchUsers();
    } catch (error) {
      const errorMsg = error.response?.data?.detail || 'Ошибка сохранения';
      showToast.error(errorMsg);
      setError(errorMsg);
    }
  };

  const handleEdit = (user) => {
    setEditingUser(user);
    setFormData({
      role: user.role || 'cleaner',
    });
    setShowModal(true);
  };

  const resetForm = () => {
    setFormData({
      role: 'cleaner',
    });
    setEditingUser(null);
  };

  const getRoleDisplayName = (roleValue) => {
    const role = roles.find((r) => r.value === roleValue);
    return role ? role.display_name : roleValue;
  };

  const filteredUsers = users.filter((user) => {
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
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Назначение ролей пользователям</h1>
        <p className="text-gray-600 mb-4">
          Назначьте роли пользователям из терминала. Только Operations Manager может изменять роли.
        </p>
        
        {/* Поиск */}
        <div className="mb-4">
          <Input
            placeholder="Поиск по имени, ID или отделу..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="max-w-md"
          />
        </div>
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
            {filteredUsers.length === 0 ? (
              <tr>
                <td colSpan="6" className="px-6 py-4 text-center text-gray-500">
                  {searchTerm ? 'Пользователи не найдены' : 'Нет пользователей'}
                </td>
              </tr>
            ) : (
              filteredUsers.map((user) => (
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
                    <Badge variant="primary">
                      {getRoleDisplayName(user.role || 'cleaner')}
                    </Badge>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <Badge variant={user.is_active ? 'success' : 'error'}>
                      {user.is_active ? 'Активен' : 'Неактивен'}
                    </Badge>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <Button variant="ghost" size="sm" onClick={() => handleEdit(user)}>
                      Изменить роль
                    </Button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        </div>

        {/* Mobile card view */}
        <div className="lg:hidden space-y-3">
          {filteredUsers.length === 0 ? (
            <div className="text-center text-gray-500 py-8">
              {searchTerm ? 'Пользователи не найдены' : 'Нет пользователей'}
            </div>
          ) : (
            filteredUsers.map((user) => (
              <div key={user.id} className="bg-white border border-gray-200 rounded-lg p-4 shadow-soft hover:shadow-medium transition-shadow duration-150">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold text-gray-900">{user.full_name || user.hikvision_id}</p>
                    <Badge variant={user.is_active ? 'success' : 'error'}>
                      {user.is_active ? 'Активен' : 'Неактивен'}
                    </Badge>
                  </div>
                  <div className="space-y-1 text-xs">
                    <div>
                      <span className="text-gray-500">ID:</span>
                      <span className="ml-1 text-gray-700 font-medium">{user.hikvision_id}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Отдел:</span>
                      <span className="ml-1 text-gray-700">{user.department || '-'}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Роль:</span>
                      <Badge variant="primary" className="ml-1">
                        {getRoleDisplayName(user.role || 'cleaner')}
                      </Badge>
                    </div>
                  </div>
                  <div className="pt-2">
                    <Button variant="ghost" size="sm" onClick={() => handleEdit(user)}>
                      Изменить роль
                    </Button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </Card>

      {/* Modal для изменения роли */}
      <Modal
        isOpen={showModal}
        onClose={() => {
          setShowModal(false);
          resetForm();
        }}
        title="Изменить роль пользователя"
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
              Сохранить
            </Button>
          </div>
        }
      >
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <p className="text-sm text-gray-600 mb-2">
              <strong>Пользователь:</strong> {editingUser?.full_name || editingUser?.hikvision_id}
            </p>
            <p className="text-sm text-gray-600">
              <strong>ID:</strong> {editingUser?.hikvision_id}
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Роль</label>
            <select
              value={formData.role}
              onChange={(e) => setFormData({ ...formData, role: e.target.value })}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-[rgb(19,91,147)] focus:ring-[rgb(19,91,147)] sm:text-sm"
              required
            >
              {roles.map((role) => (
                <option key={role.value} value={role.value}>
                  {role.display_name}
                </option>
              ))}
            </select>
          </div>
        </form>
      </Modal>
    </div>
  );
}

export default UserRolesPage;

