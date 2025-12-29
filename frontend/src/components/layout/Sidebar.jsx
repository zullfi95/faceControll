import React, { useEffect, useRef } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  UserGroupIcon,
  CalendarIcon,
  ChartBarIcon,
  Cog6ToothIcon,
  UsersIcon,
  ClockIcon,
} from '@heroicons/react/24/outline';
import { useAuth } from '../../contexts/AuthContext';

const Sidebar = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { isOperationsManager } = useAuth();
  const menuRefs = useRef([]);

  const isActive = (path) => { 
    if (path === '/') {
      return location.pathname === '/';
    }
    return location.pathname.startsWith(path);
  };

  const menuItems = [
    {
      path: '/users',
      label: 'Добавить пользователя',
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

  const allMenuItems = [...menuItems, ...(isOperationsManager() ? adminMenuItems : [])];

  // Инициализируем refs для всех элементов меню
  useEffect(() => {
    menuRefs.current = menuRefs.current.slice(0, allMenuItems.length);
  }, [allMenuItems.length]);

  // Клавиатурная навигация по меню (стрелки вверх/вниз)
  useEffect(() => {
    const handleKeyDown = (e) => {
      const currentIndex = menuRefs.current.findIndex(
        (ref) => ref === document.activeElement
      );

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        const nextIndex = currentIndex < allMenuItems.length - 1 ? currentIndex + 1 : 0;
        menuRefs.current[nextIndex]?.focus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        const prevIndex = currentIndex > 0 ? currentIndex - 1 : allMenuItems.length - 1;
        menuRefs.current[prevIndex]?.focus();
      } else if (e.key === 'Home') {
        e.preventDefault();
        menuRefs.current[0]?.focus();
      } else if (e.key === 'End') {
        e.preventDefault();
        menuRefs.current[allMenuItems.length - 1]?.focus();
      }
    };

    const sidebar = document.querySelector('aside[aria-label="Боковая панель навигации"]');
    if (sidebar) {
      sidebar.addEventListener('keydown', handleKeyDown);
      return () => sidebar.removeEventListener('keydown', handleKeyDown);
    }
  }, [allMenuItems.length]);

  return (
    <aside
      className="hidden lg:flex lg:flex-shrink-0"
      aria-label="Боковая панель навигации"
    >
      <div className="flex flex-col w-64">
        <div className="flex flex-col flex-grow bg-white border-r border-gray-200 pt-5 pb-4 overflow-y-auto">
          {/* Logo */}
          <div className="flex items-center flex-shrink-0 px-4 mb-8">
            <Link
              to="/users"
              className="flex flex-col text-2xl font-bold text-[rgb(19,91,147)] hover:text-[rgb(30,120,180)] transition-colors leading-tight"
              aria-label="WTM for Mint Services - Главная"
            >
              <span>WTM</span>
              <span className="text-sm font-normal">for Mint Services</span>
            </Link>
          </div>

          {/* Navigation */}
          <nav className="flex-1 px-2 space-y-1" aria-label="Основная навигация" role="navigation">
            {menuItems.map((item, index) => {
              const Icon = item.icon;
              const active = isActive(item.path);
              return (
                <Link
                  key={item.path}
                  ref={(el) => {
                    menuRefs.current[index] = el;
                  }}
                  to={item.path}
                  className={`
                    group flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors
                    focus:outline-none focus:ring-2 focus:ring-[rgb(19,91,147)] focus:ring-offset-2
                    ${
                      active
                        ? 'bg-[rgb(19,91,147)] text-white'
                        : 'text-gray-700 hover:bg-gray-50 hover:text-gray-900'
                    }
                  `}
                  aria-current={active ? 'page' : undefined}
                  tabIndex={0}
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

            {/* Admin section separator */}
            {isOperationsManager() && (
              <>
                <div className="pt-4 mt-4 border-t border-gray-200">
                  <div className="px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    Администрирование
                  </div>
                </div>
                {adminMenuItems.map((item, index) => {
                  const Icon = item.icon;
                  const active = isActive(item.path);
                  const adminIndex = menuItems.length + index;
                  return (
                    <Link
                      key={item.path}
                      ref={(el) => {
                        menuRefs.current[adminIndex] = el;
                      }}
                      to={item.path}
                      className={`
                        group flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors
                        focus:outline-none focus:ring-2 focus:ring-[rgb(19,91,147)] focus:ring-offset-2
                        ${
                          active
                            ? 'bg-[rgb(19,91,147)] text-white'
                            : 'text-gray-700 hover:bg-gray-50 hover:text-gray-900'
                        }
                      `}
                      aria-current={active ? 'page' : undefined}
                      tabIndex={0}
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
      </div>
    </aside>
  );
};

export default Sidebar;

