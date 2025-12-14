import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import Input from '../components/ui/Input';
import Button from '../components/ui/Button';
import { EyeIcon, EyeSlashIcon } from '@heroicons/react/24/outline';

function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [errors, setErrors] = useState({ form: '', username: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const { login, user, loading: authLoading } = useAuth();
  const navigate = useNavigate();

  // Если пользователь уже авторизован, редиректим на главную
  useEffect(() => {
    if (!authLoading && user) {
      navigate('/users', { replace: true });
    }
  }, [user, authLoading, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setErrors({ form: '', username: '', password: '' });
    setLoading(true);

    const result = await login(username, password);
    
    if (result.success) {
      // Редирект на страницу пользователей после успешного входа
      navigate('/users');
    } else {
      const errorMessage = result.error || 'Ошибка входа';
      setError(errorMessage);
      setErrors({ form: errorMessage, username: '', password: '' });
    }
    
    setLoading(false);
  };

  // Показываем загрузку пока проверяем авторизацию
  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-[rgb(19,91,147)]"></div>
          <p className="mt-4 text-gray-600">Загрузка...</p>
        </div>
      </div>
    );
  }

  // Если пользователь авторизован, не показываем форму (будет редирект)
  if (user) {
    return null;
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full">
        <div className="bg-white rounded-lg shadow-large p-8 border border-gray-200" role="main" aria-labelledby="login-title">
          <header className="text-center mb-8">
            <h1 id="login-title" className="text-3xl font-bold text-gray-900 mb-2">
              Вход в систему
            </h1>
            <p className="text-sm text-gray-600" id="login-description">
              FaceControl - Система управления доступом
            </p>
          </header>
          
          <form className="space-y-6" onSubmit={handleSubmit}>
            {(error || errors.form) && (
              <div className="rounded-md bg-red-50 border border-red-200 p-4">
                <div className="text-sm text-red-800">{error || errors.form}</div>
              </div>
            )}
            
            <Input
              label="Имя пользователя"
              id="username"
              name="username"
              type="text"
              autoComplete="username"
              required
              placeholder="Введите имя пользователя"
              value={username}
              onChange={(e) => {
                setUsername(e.target.value);
                if (errors.username) {
                  setErrors({ ...errors, username: '' });
                }
              }}
              error={errors.username}
            />
            
            <div className="relative">
              <Input
                label="Пароль"
                id="password"
                name="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                required
                placeholder="Введите пароль"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (errors.password) {
                    setErrors({ ...errors, password: '' });
                  }
                }}
                error={errors.password}
              />
              <button
                type="button"
                className="absolute right-3 top-9 text-gray-400 hover:text-gray-600"
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? (
                  <EyeSlashIcon className="h-5 w-5" />
                ) : (
                  <EyeIcon className="h-5 w-5" />
                )}
              </button>
            </div>

            <Button
              type="submit"
              disabled={loading}
              loading={loading}
              className="w-full"
            >
              Войти
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default LoginPage;

