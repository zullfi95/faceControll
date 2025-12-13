import React from 'react';

const EmptyState = ({
  icon: Icon,
  title,
  description,
  action,
  className = '',
}) => {
  return (
    <div className={`text-center py-12 px-4 ${className}`} role="region" aria-label="Пустое состояние">
      {Icon && (
        <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-gray-100 mb-4" aria-hidden="true">
          <Icon className="h-6 w-6 text-gray-400" />
        </div>
      )}
      {title && (
        <h3 className="text-lg font-medium text-gray-900 mb-2" id="empty-state-title">{title}</h3>
      )}
      {description && (
        <p className="text-sm text-gray-500 max-w-sm mx-auto mb-6" aria-describedby="empty-state-title">
          {description}
        </p>
      )}
      {action && (
        <div role="region" aria-label="Действия">
          {action}
        </div>
      )}
    </div>
  );
};

export default EmptyState;

