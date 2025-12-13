import React, { useState, useEffect, useRef } from 'react';
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

const DAYS_OF_WEEK = [
  { value: '0', label: 'Понедельник' },
  { value: '1', label: 'Вторник' },
  { value: '2', label: 'Среда' },
  { value: '3', label: 'Четверг' },
  { value: '4', label: 'Пятница' },
  { value: '5', label: 'Суббота' },
  { value: '6', label: 'Воскресенье' },
];

function WorkShiftsPage() {
  const { isOperationsManager } = useAuth();
  const [shifts, setShifts] = useState([]);
  const [users, setUsers] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showShiftModal, setShowShiftModal] = useState(false);
  const [showAssignmentModal, setShowAssignmentModal] = useState(false);
  const [editingShift, setEditingShift] = useState(null);
  const [selectedShift, setSelectedShift] = useState(null);
  const [deleteShiftConfirm, setDeleteShiftConfirm] = useState(null);
  const [deleteAssignmentConfirm, setDeleteAssignmentConfirm] = useState(null);
  const deleteShiftIdRef = useRef(null);
  const deleteAssignmentIdRef = useRef(null);

  const [shiftFormData, setShiftFormData] = useState({
    name: '',
    description: '',
    schedule: {
      '0': { start: '09:00', end: '18:00', enabled: true },
      '1': { start: '09:00', end: '18:00', enabled: true },
      '2': { start: '09:00', end: '18:00', enabled: true },
      '3': { start: '09:00', end: '18:00', enabled: true },
      '4': { start: '09:00', end: '18:00', enabled: true },
      '5': { start: '09:00', end: '18:00', enabled: false },
      '6': { start: '09:00', end: '18:00', enabled: false },
    },
    is_active: true,
  });

  const [assignmentFormData, setAssignmentFormData] = useState({
    user_id: '',
    shift_id: '',
    start_date: '',
    end_date: '',
    is_active: true,
  });

  useEffect(() => {
    if (isOperationsManager()) {
      fetchShifts();
      fetchUsers();
      fetchAssignments();
    }
  }, [isOperationsManager]);

  const fetchShifts = async () => {
    try {
      const response = await axios.get('/api/work-shifts/');
      setShifts(response.data);
    } catch (error) {
      setError('Ошибка загрузки смен');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const fetchUsers = async () => {
    try {
      const response = await axios.get('/api/users/');
      setUsers(response.data);
    } catch (error) {
      console.error('Failed to fetch users:', error);
    }
  };

  const fetchAssignments = async () => {
    try {
      const response = await axios.get('/api/user-shift-assignments/');
      setAssignments(response.data);
    } catch (error) {
      console.error('Failed to fetch assignments:', error);
    }
  };

  const handleShiftSubmit = async (e) => {
    e.preventDefault();
    setError('');

    try {
      // Преобразуем schedule в правильный формат (если нужно)
      const dataToSend = {
        ...shiftFormData,
        schedule: shiftFormData.schedule
      };
      
      if (editingShift) {
        await axios.put(`/api/work-shifts/${editingShift.id}`, dataToSend);
      } else {
        await axios.post('/api/work-shifts/', dataToSend);
      }
      
      setShowShiftModal(false);
      setEditingShift(null);
      resetShiftForm();
      showToast.success(editingShift ? 'Смена успешно обновлена' : 'Смена успешно создана');
      fetchShifts();
    } catch (error) {
      const errorMessage = error.response?.data?.detail;
      let errorMsg = 'Ошибка сохранения';
      if (Array.isArray(errorMessage)) {
        errorMsg = errorMessage.map(err => err.msg || JSON.stringify(err)).join(', ');
      } else if (typeof errorMessage === 'object') {
        errorMsg = JSON.stringify(errorMessage);
      } else if (errorMessage) {
        errorMsg = errorMessage;
      } else if (error.message) {
        errorMsg = error.message;
      }
      showToast.error(errorMsg);
      setError(errorMsg);
    }
  };

  const handleAssignmentSubmit = async (e) => {
    e.preventDefault();
    setError('');

    try {
      const data = {
        user_id: parseInt(assignmentFormData.user_id),
        shift_id: parseInt(assignmentFormData.shift_id),
        start_date: assignmentFormData.start_date && assignmentFormData.start_date.trim() !== '' 
          ? assignmentFormData.start_date 
          : null,
        end_date: assignmentFormData.end_date && assignmentFormData.end_date.trim() !== '' 
          ? assignmentFormData.end_date 
          : null,
        is_active: assignmentFormData.is_active,
      };
      
      await axios.post('/api/user-shift-assignments/', data);
      
      setShowAssignmentModal(false);
      resetAssignmentForm();
      showToast.success('Сотрудник успешно привязан к смене');
      fetchAssignments();
    } catch (error) {
      const errorMessage = error.response?.data?.detail;
      let errorMsg = 'Ошибка сохранения';
      if (Array.isArray(errorMessage)) {
        errorMsg = errorMessage.map(err => err.msg || JSON.stringify(err)).join(', ');
      } else if (typeof errorMessage === 'object') {
        errorMsg = JSON.stringify(errorMessage);
      } else if (errorMessage) {
        errorMsg = errorMessage;
      } else if (error.message) {
        errorMsg = error.message;
      }
      showToast.error(errorMsg);
      setError(errorMsg);
    }
  };


  const handleEditShift = (shift) => {
    setEditingShift(shift);
    setShiftFormData({
      name: shift.name,
      description: shift.description || '',
      schedule: shift.schedule || shiftFormData.schedule,
      is_active: shift.is_active,
    });
    setShowShiftModal(true);
  };

  const handleAssignUsers = (shift) => {
    setSelectedShift(shift);
    setAssignmentFormData({
      ...assignmentFormData,
      shift_id: shift.id.toString(),
    });
    setShowAssignmentModal(true);
  };

  const confirmDeleteShift = async () => {
    const shiftId = deleteShiftIdRef.current;
    if (!shiftId) {
      setDeleteShiftConfirm(null);
      deleteShiftIdRef.current = null;
      return;
    }
    
    try {
      await axios.delete(`/api/work-shifts/${shiftId}`);
      showToast.success('Смена успешно удалена');
      fetchShifts();
      fetchAssignments();
    } catch (error) {
      const errorMessage = error.response?.data?.detail;
      let errorMsg = 'Ошибка удаления';
      if (Array.isArray(errorMessage)) {
        errorMsg = errorMessage.map(err => err.msg || JSON.stringify(err)).join(', ');
      } else if (typeof errorMessage === 'object') {
        errorMsg = JSON.stringify(errorMessage);
      } else if (errorMessage) {
        errorMsg = errorMessage;
      } else if (error.message) {
        errorMsg = error.message;
      }
      showToast.error(errorMsg);
      setError(errorMsg);
    } finally {
      setDeleteShiftConfirm(null);
      deleteShiftIdRef.current = null;
    }
  };

  const confirmDeleteAssignment = async () => {
    const assignmentId = deleteAssignmentIdRef.current;
    if (!assignmentId) {
      setDeleteAssignmentConfirm(null);
      deleteAssignmentIdRef.current = null;
      return;
    }
    
    try {
      await axios.delete(`/api/user-shift-assignments/${assignmentId}`);
      showToast.success('Привязка успешно удалена');
      fetchAssignments();
    } catch (error) {
      const errorMessage = error.response?.data?.detail;
      let errorMsg = 'Ошибка удаления';
      if (Array.isArray(errorMessage)) {
        errorMsg = errorMessage.map(err => err.msg || JSON.stringify(err)).join(', ');
      } else if (typeof errorMessage === 'object') {
        errorMsg = JSON.stringify(errorMessage);
      } else if (errorMessage) {
        errorMsg = errorMessage;
      } else if (error.message) {
        errorMsg = error.message;
      }
      showToast.error(errorMsg);
      setError(errorMsg);
    } finally {
      setDeleteAssignmentConfirm(null);
      deleteAssignmentIdRef.current = null;
    }
  };

  const resetShiftForm = () => {
    setShiftFormData({
      name: '',
      description: '',
      schedule: {
        '0': { start: '09:00', end: '18:00', enabled: true },
        '1': { start: '09:00', end: '18:00', enabled: true },
        '2': { start: '09:00', end: '18:00', enabled: true },
        '3': { start: '09:00', end: '18:00', enabled: true },
        '4': { start: '09:00', end: '18:00', enabled: true },
        '5': { start: '09:00', end: '18:00', enabled: false },
        '6': { start: '09:00', end: '18:00', enabled: false },
      },
      is_active: true,
    });
    setEditingShift(null);
  };

  const resetAssignmentForm = () => {
    setAssignmentFormData({
      user_id: '',
      shift_id: selectedShift?.id?.toString() || '',
      start_date: '',
      end_date: '',
      is_active: true,
    });
  };

  const updateDaySchedule = (day, field, value) => {
    setShiftFormData({
      ...shiftFormData,
      schedule: {
        ...shiftFormData.schedule,
        [day]: {
          ...shiftFormData.schedule[day],
          [field]: field === 'enabled' ? value : value,
        },
      },
    });
  };

  const getShiftAssignments = (shiftId) => {
    return assignments.filter(a => a.shift_id === shiftId && a.is_active);
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
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div role="main">
      <header className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900" id="work-shifts-title">
            Управление рабочими сменами
          </h1>
          <p className="text-gray-600 mt-1" id="work-shifts-description">
            Создавайте смены и привязывайте сотрудников
          </p>
        </div>
        <Button
          onClick={() => {
            resetShiftForm();
            setShowShiftModal(true);
          }}
        >
          Создать смену
        </Button>
      </header>

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 rounded-md p-4">
          <p className="text-red-800">{error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6">
        {shifts.map((shift) => {
          const shiftAssignments = getShiftAssignments(shift.id);
          return (
            <Card key={shift.id}>
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">{shift.name}</h3>
                  {shift.description && (
                    <p className="text-sm text-gray-600 mt-1">{shift.description}</p>
                  )}
                  <div className="mt-2 flex items-center gap-2">
                    <Badge variant={shift.is_active ? 'success' : 'error'}>
                      {shift.is_active ? 'Активна' : 'Неактивна'}
                    </Badge>
                    <span className="text-sm text-gray-600">
                      Привязано пользователей: {shift.user_count || shiftAssignments.length}
                    </span>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="ghost" size="sm" onClick={() => handleAssignUsers(shift)}>
                    Привязать сотрудников
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => handleEditShift(shift)}>
                    Редактировать
                  </Button>
                  <Button variant="error" size="sm" onClick={() => {
                    deleteShiftIdRef.current = shift.id;
                    setDeleteShiftConfirm(shift.id);
                  }}>
                    Удалить
                  </Button>
                </div>
              </div>

              {/* Расписание по дням */}
              <div className="mt-4">
                <h4 className="text-sm font-medium text-gray-700 mb-2">Расписание:</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  {DAYS_OF_WEEK.map((day) => {
                    const daySchedule = shift.schedule?.[day.value] || { start: '-', end: '-', enabled: false };
                    return (
                      <div
                        key={day.value}
                        className={`p-2 rounded text-xs ${
                          daySchedule.enabled
                            ? 'bg-blue-50 border border-blue-200'
                            : 'bg-gray-50 border border-gray-200'
                        }`}
                      >
                        <div className="font-medium">{day.label}</div>
                        {daySchedule.enabled ? (
                          <div className="text-gray-600">
                            {daySchedule.start} - {daySchedule.end}
                          </div>
                        ) : (
                          <div className="text-gray-400">Выходной</div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Привязанные пользователи */}
              {shiftAssignments.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Привязанные сотрудники:</h4>
                  <div className="space-y-1">
                    {shiftAssignments.map((assignment) => (
                      <div
                        key={assignment.id}
                        className="flex justify-between items-center p-2 bg-gray-50 rounded text-sm"
                      >
                        <span>{assignment.user_name || `User ID: ${assignment.user_id}`}</span>
                        <Button
                          variant="error"
                          size="sm"
                          onClick={() => {
                            deleteAssignmentIdRef.current = assignment.id;
                            setDeleteAssignmentConfirm(assignment.id);
                          }}
                        >
                          Удалить
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </Card>
          );
        })}
      </div>

      {shifts.length === 0 && (
        <Card>
          <div className="text-center py-12">
            <p className="text-gray-500">Нет созданных смен. Создайте первую смену.</p>
          </div>
        </Card>
      )}

      {deleteShiftConfirm && (
        <ConfirmDialog
          isOpen={true}
          onClose={() => {
            setDeleteShiftConfirm(null);
            deleteShiftIdRef.current = null;
          }}
          onConfirm={confirmDeleteShift}
          title="Удаление смены"
          message="Вы уверены, что хотите удалить эту смену?"
          confirmText="Удалить"
          cancelText="Отмена"
          variant="error"
        />
      )}

      {deleteAssignmentConfirm && (
        <ConfirmDialog
          isOpen={true}
          onClose={() => {
            setDeleteAssignmentConfirm(null);
            deleteAssignmentIdRef.current = null;
          }}
          onConfirm={confirmDeleteAssignment}
          title="Удаление привязки"
          message="Вы уверены, что хотите удалить эту привязку?"
          confirmText="Удалить"
          cancelText="Отмена"
          variant="error"
        />
      )}

      {/* Modal для создания/редактирования смены */}
      <Modal
        isOpen={showShiftModal}
        onClose={() => {
          setShowShiftModal(false);
          resetShiftForm();
        }}
        title={editingShift ? 'Редактировать смену' : 'Создать смену'}
        size="lg"
        footer={
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              onClick={() => {
                setShowShiftModal(false);
                resetShiftForm();
              }}
            >
              Отмена
            </Button>
            <Button onClick={handleShiftSubmit}>
              {editingShift ? 'Сохранить' : 'Создать'}
            </Button>
          </div>
        }
      >
        <form onSubmit={handleShiftSubmit}>
          <div className="space-y-4">
            <Input
              label="Название смены"
              type="text"
              required
              value={shiftFormData.name}
              onChange={(e) => setShiftFormData({ ...shiftFormData, name: e.target.value })}
            />

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Описание</label>
              <textarea
                value={shiftFormData.description}
                onChange={(e) => setShiftFormData({ ...shiftFormData, description: e.target.value })}
                rows={2}
                className="block w-full rounded-md border-gray-300 shadow-sm focus:border-[rgb(19,91,147)] focus:ring-[rgb(19,91,147)] sm:text-sm"
              />
            </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">Расписание по дням недели</label>
                      <div className="space-y-2">
                        {DAYS_OF_WEEK.map((day) => {
                          const daySchedule = shiftFormData.schedule[day.value];
                          return (
                            <div
                              key={day.value}
                              className="flex items-center space-x-4 p-3 border border-gray-200 rounded-md"
                            >
                              <div className="flex items-center">
                                <input
                                  type="checkbox"
                                  checked={daySchedule.enabled}
                                  onChange={(e) => updateDaySchedule(day.value, 'enabled', e.target.checked)}
                                  className="rounded border-gray-300 text-[rgb(19,91,147)] focus:ring-[rgb(19,91,147)]"
                                />
                                <label className="ml-2 text-sm font-medium text-gray-700 w-24">
                                  {day.label}
                                </label>
                              </div>
                              {daySchedule.enabled && (
                                <>
                                  <input
                                    type="time"
                                    value={daySchedule.start}
                                    onChange={(e) => updateDaySchedule(day.value, 'start', e.target.value)}
                                    className="border border-gray-300 rounded-md px-2 py-1 text-sm"
                                  />
                                  <span className="text-gray-500">-</span>
                                  <input
                                    type="time"
                                    value={daySchedule.end}
                                    onChange={(e) => updateDaySchedule(day.value, 'end', e.target.value)}
                                    className="border border-gray-300 rounded-md px-2 py-1 text-sm"
                                  />
                                </>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    <div>
                      <label className="flex items-center">
                        <input
                          type="checkbox"
                          checked={shiftFormData.is_active}
                          onChange={(e) => setShiftFormData({ ...shiftFormData, is_active: e.target.checked })}
                          className="rounded border-gray-300 text-[rgb(19,91,147)] focus:ring-[rgb(19,91,147)]"
                        />
                        <span className="ml-2 text-sm text-gray-700">Активна</span>
                      </label>
                    </div>
                  </div>
        </form>
      </Modal>

      {/* Modal для привязки пользователей */}
      <Modal
        isOpen={showAssignmentModal}
        onClose={() => {
          setShowAssignmentModal(false);
          resetAssignmentForm();
        }}
        title="Привязать сотрудника к смене"
        footer={
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              onClick={() => {
                setShowAssignmentModal(false);
                resetAssignmentForm();
              }}
            >
              Отмена
            </Button>
            <Button onClick={handleAssignmentSubmit}>
              Привязать
            </Button>
          </div>
        }
      >
        <form onSubmit={handleAssignmentSubmit}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Смена</label>
              <select
                value={assignmentFormData.shift_id}
                onChange={(e) => setAssignmentFormData({ ...assignmentFormData, shift_id: e.target.value })}
                className="block w-full rounded-md border-gray-300 shadow-sm focus:border-[rgb(19,91,147)] focus:ring-[rgb(19,91,147)] sm:text-sm"
                required
              >
                <option value="">Выберите смену</option>
                {shifts.map((shift) => (
                  <option key={shift.id} value={shift.id}>
                    {shift.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Сотрудник</label>
              <select
                value={assignmentFormData.user_id}
                onChange={(e) => setAssignmentFormData({ ...assignmentFormData, user_id: e.target.value })}
                className="block w-full rounded-md border-gray-300 shadow-sm focus:border-[rgb(19,91,147)] focus:ring-[rgb(19,91,147)] sm:text-sm"
                required
              >
                <option value="">Выберите сотрудника</option>
                {users.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.full_name || user.hikvision_id}
                  </option>
                ))}
              </select>
            </div>

            <Input
              label="Дата начала (опционально)"
              type="date"
              value={assignmentFormData.start_date}
              onChange={(e) => setAssignmentFormData({ ...assignmentFormData, start_date: e.target.value })}
            />

            <Input
              label="Дата окончания (опционально)"
              type="date"
              value={assignmentFormData.end_date}
              onChange={(e) => setAssignmentFormData({ ...assignmentFormData, end_date: e.target.value })}
            />

            <div>
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={assignmentFormData.is_active}
                  onChange={(e) => setAssignmentFormData({ ...assignmentFormData, is_active: e.target.checked })}
                  className="rounded border-gray-300 text-[rgb(19,91,147)] focus:ring-[rgb(19,91,147)]"
                />
                <span className="ml-2 text-sm text-gray-700">Активна</span>
              </label>
            </div>
          </div>
        </form>
      </Modal>
    </div>
  );
}

export default WorkShiftsPage;

