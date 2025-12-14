import { useEffect, useCallback, useRef } from 'react';

/**
 * Хук для глобальной клавиатурной навигации
 * Поддерживает горячие клавиши и управление фокусом
 */
export const useKeyboardNavigation = (shortcuts = {}) => {
  useEffect(() => {
    const handleKeyDown = (event) => {
      // Игнорируем, если пользователь вводит текст в input/textarea
      if (
        event.target.tagName === 'INPUT' ||
        event.target.tagName === 'TEXTAREA' ||
        event.target.isContentEditable
      ) {
        // Разрешаем только Escape и Ctrl/Cmd комбинации
        if (event.key === 'Escape' || event.ctrlKey || event.metaKey) {
          // Продолжаем обработку
        } else {
          return;
        }
      }

      // Обработка горячих клавиш
      const key = event.key.toLowerCase();
      const keyCombo = `${event.ctrlKey || event.metaKey ? 'ctrl+' : ''}${event.shiftKey ? 'shift+' : ''}${event.altKey ? 'alt+' : ''}${key}`;
      
      if (shortcuts[keyCombo]) {
        event.preventDefault();
        shortcuts[keyCombo](event);
        return;
      }

      // Обработка отдельных клавиш
      if (shortcuts[key]) {
        event.preventDefault();
        shortcuts[key](event);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [shortcuts]);
};

/**
 * Хук для управления фокусом в модальных окнах
 */
export const useFocusTrap = (isActive, containerRef) => {
  useEffect(() => {
    if (!isActive || !containerRef.current) return;

    const container = containerRef.current;
    const focusableElements = container.querySelectorAll(
      'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    
    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];

    const handleTabKey = (e) => {
      if (e.key !== 'Tab') return;

      if (e.shiftKey) {
        // Shift + Tab
        if (document.activeElement === firstElement) {
          e.preventDefault();
          lastElement?.focus();
        }
      } else {
        // Tab
        if (document.activeElement === lastElement) {
          e.preventDefault();
          firstElement?.focus();
        }
      }
    };

    // Фокусируем первый элемент при открытии
    firstElement?.focus();

    container.addEventListener('keydown', handleTabKey);
    return () => {
      container.removeEventListener('keydown', handleTabKey);
    };
  }, [isActive, containerRef]);
};

/**
 * Хук для восстановления фокуса после закрытия модального окна
 */
export const useRestoreFocus = (isOpen, triggerRef) => {
  const previousFocusRef = useRef(null);

  useEffect(() => {
    if (isOpen) {
      // Сохраняем элемент, который был в фокусе
      previousFocusRef.current = document.activeElement;
    } else {
      // Восстанавливаем фокус
      if (previousFocusRef.current && previousFocusRef.current.focus) {
        setTimeout(() => {
          previousFocusRef.current?.focus();
        }, 100);
      } else if (triggerRef?.current) {
        setTimeout(() => {
          triggerRef.current?.focus();
        }, 100);
      }
    }
  }, [isOpen, triggerRef]);
};

