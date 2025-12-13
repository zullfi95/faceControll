import React from 'react';

/**
 * Skip Link компонент для accessibility
 * Позволяет пользователям клавиатуры быстро перейти к основному контенту
 */
const SkipLink = ({ href = '#main-content', children = 'Перейти к основному контенту' }) => {
  return (
    <a
      href={href}
      className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-[rgb(19,91,147)] focus:text-white focus:rounded-md focus:shadow-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[rgb(19,91,147)]"
      onClick={(e) => {
        e.preventDefault();
        const target = document.querySelector(href);
        if (target) {
          target.focus();
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }}
    >
      {children}
    </a>
  );
};

export default SkipLink;

