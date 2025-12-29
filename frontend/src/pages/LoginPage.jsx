import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import Input from '../components/ui/Input';
import Button from '../components/ui/Button';
import { EyeIcon, EyeSlashIcon, LockClosedIcon, UserIcon } from '@heroicons/react/24/outline';
import { motion, AnimatePresence } from 'framer-motion';

function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [errors, setErrors] = useState({ form: '', username: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [isFocused, setIsFocused] = useState({ username: false, password: false });
  const { login, user, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const usernameInputRef = useRef(null);

  // Автофокус на поле username при загрузке
  useEffect(() => {
    if (!authLoading && !user && usernameInputRef.current) {
      // Небольшая задержка для плавности
      setTimeout(() => {
        usernameInputRef.current?.focus();
      }, 100);
    }
  }, [authLoading, user]);

  // Если пользователь уже авторизован, редиректим на главную
  useEffect(() => {
    if (!authLoading && user) {
      navigate('/users', { replace: true });
    }
  }, [user, authLoading, navigate]);

  // Валидация в реальном времени
  const validateForm = () => {
    const newErrors = { form: '', username: '', password: '' };
    let isValid = true;

    if (!username.trim()) {
      newErrors.username = 'Имя пользователя обязательно';
      isValid = false;
    } else if (username.trim().length < 3) {
      newErrors.username = 'Имя пользователя должно содержать минимум 3 символа';
      isValid = false;
    }

    if (!password) {
      newErrors.password = 'Пароль обязателен';
      isValid = false;
    } else if (password.length < 4) {
      newErrors.password = 'Пароль должен содержать минимум 4 символа';
      isValid = false;
    }

    setErrors(newErrors);
    return isValid;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setErrors({ form: '', username: '', password: '' });

    // Валидация перед отправкой
    if (!validateForm()) {
      return;
    }

    setLoading(true);

    try {
      const result = await login(username.trim(), password);
      
      if (result.success) {
        // Небольшая задержка для визуальной обратной связи
        await new Promise(resolve => setTimeout(resolve, 300));
        navigate('/users');
      } else {
        const errorMessage = result.error || 'Ошибка входа';
        setError(errorMessage);
        setErrors({ form: errorMessage, username: '', password: '' });
        
        // Фокус на поле username при ошибке
        usernameInputRef.current?.focus();
      }
    } catch (err) {
      const errorMessage = 'Произошла ошибка при входе. Попробуйте еще раз.';
      setError(errorMessage);
      setErrors({ form: errorMessage, username: '', password: '' });
    } finally {
      setLoading(false);
    }
  };

  // Обработка Enter для отправки формы
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !loading) {
      handleSubmit(e);
    }
  };

  // Показываем загрузку пока проверяем авторизацию
  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 via-blue-50 to-gray-100">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-center"
        >
          <div className="inline-block animate-spin rounded-full h-10 w-10 border-2 border-[rgb(19,91,147)] border-t-transparent"></div>
          <p className="mt-4 text-gray-600 font-medium">Загрузка...</p>
        </motion.div>
      </div>
    );
  }

  // Если пользователь авторизован, не показываем форму (будет редирект)
  if (user) {
    return null;
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 via-blue-50 to-gray-100 py-12 px-4 sm:px-6 lg:px-8">
      {/* Декоративные элементы фона */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-[rgb(19,91,147)] opacity-5 rounded-full blur-3xl"></div>
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-[rgb(19,91,147)] opacity-5 rounded-full blur-3xl"></div>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="max-w-md w-full relative z-10"
      >
        <div className="bg-white rounded-2xl shadow-large p-8 sm:p-10 border border-gray-100" role="main" aria-labelledby="login-title">
          <header className="text-center mb-8">
            {/* Logo с улучшенным дизайном */}
            <motion.div
              initial={{ scale: 0.9 }}
              animate={{ scale: 1 }}
              transition={{ delay: 0.1 }}
              className="mb-8"
            >
              <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-[rgb(19,91,147)] to-[rgb(30,120,180)] shadow-medium mb-4">
                <LockClosedIcon className="h-10 w-10 text-white" />
              </div>
              <h1 className="text-4xl font-bold text-[rgb(19,91,147)] mb-2 tracking-tight">
                WTM
              </h1>
              <p className="text-sm font-semibold text-gray-700 mb-1 tracking-wide">
                Wach traffic monitoring system
              </p>
              <p className="text-xs text-gray-500 font-medium">
                Created by Sci-fi
              </p>
            </motion.div>
            
            <div className="border-t border-gray-200 pt-6 mt-6">
              <h2 id="login-title" className="text-2xl font-bold text-gray-900 mb-2">
                Вход в систему
              </h2>
              <p className="text-sm text-gray-600" id="login-description">
                WTM for Mint Services - Система управления доступом
              </p>
            </div>
          </header>
          
          <form className="space-y-5" onSubmit={handleSubmit} noValidate>
            {/* Сообщение об ошибке с анимацией */}
            <AnimatePresence>
              {(error || errors.form) && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="rounded-lg bg-red-50 border border-red-200 p-4"
                  role="alert"
                  aria-live="assertive"
                >
                  <div className="flex items-start">
                    <div className="flex-shrink-0">
                      <svg className="h-5 w-5 text-red-600" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                      </svg>
                    </div>
                    <div className="ml-3 flex-1">
                      <p className="text-sm font-medium text-red-800">{error || errors.form}</p>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
            
            {/* Поле Username с улучшенным дизайном */}
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <UserIcon className={`h-5 w-5 ${isFocused.username ? 'text-[rgb(19,91,147)]' : 'text-gray-400'} transition-colors duration-200`} />
              </div>
              <Input
                ref={usernameInputRef}
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
                  if (errors.username || errors.form) {
                    setErrors({ ...errors, username: '', form: '' });
                    setError('');
                  }
                }}
                onFocus={() => setIsFocused({ ...isFocused, username: true })}
                onBlur={() => {
                  setIsFocused({ ...isFocused, username: false });
                  if (username && !errors.username) {
                    validateForm();
                  }
                }}
                onKeyDown={handleKeyDown}
                error={errors.username}
                className="pl-10"
                disabled={loading}
              />
            </div>
            
            {/* Поле Password с улучшенным дизайном */}
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <LockClosedIcon className={`h-5 w-5 ${isFocused.password ? 'text-[rgb(19,91,147)]' : 'text-gray-400'} transition-colors duration-200`} />
              </div>
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
                  if (errors.password || errors.form) {
                    setErrors({ ...errors, password: '', form: '' });
                    setError('');
                  }
                }}
                onFocus={() => setIsFocused({ ...isFocused, password: true })}
                onBlur={() => {
                  setIsFocused({ ...isFocused, password: false });
                  if (password && !errors.password) {
                    validateForm();
                  }
                }}
                onKeyDown={handleKeyDown}
                error={errors.password}
                className="pl-10 pr-10"
                disabled={loading}
              />
              <button
                type="button"
                className="absolute right-3 top-9 p-1.5 text-gray-400 hover:text-gray-600 focus:outline-none focus:ring-2 focus:ring-[rgb(19,91,147)] focus:ring-offset-2 rounded-md transition-colors duration-200"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'}
                tabIndex={0}
                disabled={loading}
              >
                {showPassword ? (
                  <EyeSlashIcon className="h-5 w-5" />
                ) : (
                  <EyeIcon className="h-5 w-5" />
                )}
              </button>
            </div>

            {/* Кнопка входа с улучшенным дизайном */}
            <motion.div
              whileHover={{ scale: loading ? 1 : 1.01 }}
              whileTap={{ scale: loading ? 1 : 0.99 }}
            >
              <Button
                type="submit"
                disabled={loading || !username.trim() || !password}
                loading={loading}
                className="w-full py-3 text-base font-semibold shadow-medium"
                aria-label="Войти в систему"
              >
                {loading ? 'Вход...' : 'Войти'}
              </Button>
            </motion.div>
          </form>

          {/* Дополнительная информация */}
          <div className="mt-6 pt-6 border-t border-gray-200">
            <p className="text-xs text-center text-gray-500">
              Используйте учетные данные, предоставленные администратором
            </p>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

export default LoginPage;

