import React, { useEffect, useRef } from 'react';

/**
 * Live Region компонент для accessibility
 * Объявляет изменения контента для screen readers
 */
const LiveRegion = ({ 
  message, 
  priority = 'polite', // 'polite' | 'assertive' | 'off'
  className = '' 
}) => {
  const regionRef = useRef(null);

  useEffect(() => {
    if (message && regionRef.current) {
      // Очищаем предыдущее сообщение для повторного объявления
      regionRef.current.textContent = '';
      setTimeout(() => {
        if (regionRef.current) {
          regionRef.current.textContent = message;
        }
      }, 100);
    }
  }, [message]);

  return (
    <div
      ref={regionRef}
      role="status"
      aria-live={priority}
      aria-atomic="true"
      className={`sr-only ${className}`}
    >
      {message}
    </div>
  );
};

export default LiveRegion;

