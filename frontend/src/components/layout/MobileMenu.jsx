import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  UserGroupIcon,
  CalendarIcon,
  ChartBarIcon,
  Cog6ToothIcon,
  UsersIcon,
  ClockIcon,
  XMarkIcon,
  Bars3Icon,
} from '@heroicons/react/24/outline';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../../contexts/AuthContext';

const MobileMenu = () => {
  const [isOpen, setIsOpen] = useState(false);
  const location = useLocation();
  const { isOperationsManager } = useAuth();

  // Закрываем меню при изменении маршрута
  useEffect(() => {
    setIsOpen(false);
  }, [location.pathname]);

  // Блокируем скролл body когда меню открыто
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isOpen]);

  const isActive = (path) => {
    if (path === '/') {
      return location.pathname === '/';
    }
    return location.pathname.startsWith(path);
  };

  const menuItems = [
    {
      path: '/users',
      label: 'Сотрудники',
      icon: UserGroupIcon,
    },
    {
      path: '/events',
      label: 'События',
      icon: CalendarIcon,
    },
    {
      path: '/reports',
      label: 'Отчеты',
      icon: ChartBarIcon,
    },
    {
      path: '/settings',
      label: 'Настройки',
      icon: Cog6ToothIcon,
    },
  ];

  const adminMenuItems = [
    {
      path: '/users-management',
      label: 'Пользователи и роли',
      icon: UsersIcon,
    },
    {
      path: '/work-shifts',
      label: 'Рабочие смены',
      icon: ClockIcon,
    },
  ];

  return (
    <>
      {/* Burger button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="lg:hidden p-2 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-[rgb(19,91,147)] focus:ring-offset-2"
        aria-label="Открыть меню"
        aria-expanded={isOpen}
        aria-controls="mobile-menu"
      >
        {isOpen ? (
          <XMarkIcon className="h-6 w-6" aria-hidden="true" />
        ) : (
          <Bars3Icon className="h-6 w-6" aria-hidden="true" />
        )}
      </button>

      {/* Mobile menu overlay */}
      <AnimatePresence>
        {isOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40 bg-gray-600 bg-opacity-75 lg:hidden"
              onClick={() => setIsOpen(false)}
              aria-hidden="true"
            />

            {/* Menu panel */}
            <motion.div
              initial={{ x: -300 }}
              animate={{ x: 0 }}
              exit={{ x: -300 }}
              transition={{ type: 'tween', duration: 0.2 }}
              className="fixed inset-y-0 left-0 z-50 w-64 bg-white shadow-xl lg:hidden"
              id="mobile-menu"
              role="dialog"
              aria-modal="true"
              aria-label="Мобильное меню"
            >
              <div className="flex flex-col h-full">
                {/* Header */}
                <div className="flex items-center justify-between px-4 py-4 border-b border-gray-200">
                  <Link
                    to="/users"
                    onClick={() => setIsOpen(false)}
                    className="flex flex-col text-xl font-bold text-[rgb(19,91,147)] hover:text-[rgb(30,120,180)] transition-colors leading-tight"
                  >
                    <span>WTM</span>
                    <span className="text-xs font-normal">for Mint Services</span>
                  </Link>
                  <button
                    onClick={() => setIsOpen(false)}
                    className="p-2 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-[rgb(19,91,147)]"
                    aria-label="Закрыть меню"
                  >
                    <XMarkIcon className="h-6 w-6" aria-hidden="true" />
                  </button>
                </div>

                {/* Navigation */}
                <nav className="flex-1 px-2 py-4 space-y-1 overflow-y-auto" aria-label="Мобильная навигация">
                  {menuItems.map((item) => {
                    const Icon = item.icon;
                    const active = isActive(item.path);
                    return (
                      <Link
                        key={item.path}
                        to={item.path}
                        onClick={() => setIsOpen(false)}
                        className={`
                          group flex items-center px-3 py-2 text-base font-medium rounded-md transition-colors
                          ${
                            active
                              ? 'bg-[rgb(19,91,147)] text-white'
                              : 'text-gray-700 hover:bg-gray-50 hover:text-gray-900'
                          }
                        `}
                        aria-current={active ? 'page' : undefined}
                      >
                        <Icon
                          className={`
                            mr-3 flex-shrink-0 h-6 w-6
                            ${active ? 'text-white' : 'text-gray-400 group-hover:text-gray-500'}
                          `}
                          aria-hidden="true"
                        />
                        {item.label}
                      </Link>
                    );
                  })}

                  {/* Admin section */}
                  {isOperationsManager() && (
                    <>
                      <div className="pt-4 mt-4 border-t border-gray-200">
                        <div className="px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                          Администрирование
                        </div>
                      </div>
                      {adminMenuItems.map((item) => {
                        const Icon = item.icon;
                        const active = isActive(item.path);
                        return (
                          <Link
                            key={item.path}
                            to={item.path}
                            onClick={() => setIsOpen(false)}
                            className={`
                              group flex items-center px-3 py-2 text-base font-medium rounded-md transition-colors
                              ${
                                active
                                  ? 'bg-[rgb(19,91,147)] text-white'
                                  : 'text-gray-700 hover:bg-gray-50 hover:text-gray-900'
                              }
                            `}
                            aria-current={active ? 'page' : undefined}
                          >
                            <Icon
                              className={`
                                mr-3 flex-shrink-0 h-6 w-6
                                ${active ? 'text-white' : 'text-gray-400 group-hover:text-gray-500'}
                              `}
                              aria-hidden="true"
                            />
                            {item.label}
                          </Link>
                        );
                      })}
                    </>
                  )}
                </nav>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
};

export default MobileMenu;

