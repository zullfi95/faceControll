import React from 'react';
import { motion } from 'framer-motion';

const Card = ({
  children,
  title,
  subtitle,
  actions,
  className = '',
  hover = false,
  role = 'region',
  'aria-labelledby': ariaLabelledBy,
  'aria-describedby': ariaDescribedBy,
  ...props
}) => {
  const titleId = title ? `card-title-${Math.random().toString(36).substr(2, 9)}` : undefined;
  const subtitleId = subtitle ? `card-subtitle-${Math.random().toString(36).substr(2, 9)}` : undefined;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={`
        bg-white rounded-lg border border-gray-200 shadow-card
        ${hover ? 'transition-shadow duration-200 hover:shadow-card-hover' : ''}
        ${className}
      `}
      role={role}
      aria-labelledby={ariaLabelledBy || titleId}
      aria-describedby={ariaDescribedBy || subtitleId}
      {...props}
    >
      {(title || subtitle || actions) && (
        <header className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            {title && (
              <h3 id={titleId} className="text-lg font-semibold text-gray-900">{title}</h3>
            )}
            {subtitle && (
              <p id={subtitleId} className="mt-1 text-sm text-gray-500">{subtitle}</p>
            )}
          </div>
          {actions && (
            <div className="flex items-center gap-2" role="group" aria-label="Действия с карточкой">
              {actions}
            </div>
          )}
        </header>
      )}
      <div className={title || subtitle || actions ? 'px-6 py-4' : 'p-6'}>
        {children}
      </div>
    </motion.div>
  );
};

export default Card;

