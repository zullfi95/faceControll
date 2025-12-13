import React from 'react';
import Modal from './Modal';
import Button from './Button';
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline';

const ConfirmDialog = ({
  isOpen,
  onClose,
  onConfirm,
  title = 'Подтверждение',
  message,
  confirmText = 'Подтвердить',
  cancelText = 'Отмена',
  variant = 'error',
  ...props
}) => {
  const titleId = `confirm-title-${Math.random().toString(36).substr(2, 9)}`;
  const messageId = `confirm-message-${Math.random().toString(36).substr(2, 9)}`;
  const handleConfirm = async () => {
    if (onConfirm) {
      // onConfirm может быть синхронной или асинхронной функцией
      // Большинство onConfirm функций сами управляют закрытием диалога
      await onConfirm();
    }
  };
  
  const iconColors = {
    error: 'text-red-600',
    warning: 'text-amber-600',
    info: 'text-blue-600',
  };
  
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size="sm"
      role="alertdialog"
      aria-labelledby={titleId}
      aria-describedby={messageId}
      {...props}
    >
      <div className="flex items-start gap-4">
        <div className={`flex-shrink-0 ${iconColors[variant]}`} aria-hidden="true">
          <ExclamationTriangleIcon className="h-6 w-6" />
        </div>
        <div className="flex-1">
          <h3 id={titleId} className="text-lg font-semibold text-gray-900 mb-2">{title}</h3>
          <p id={messageId} className="text-sm text-gray-600">{message}</p>
        </div>
      </div>
      <div className="mt-6 flex justify-end gap-3" role="group" aria-label="Действия подтверждения">
        <Button variant="secondary" onClick={onClose}>
          {cancelText}
        </Button>
        <Button
          variant={variant === 'error' ? 'error' : variant === 'warning' ? 'warning' : 'primary'}
          onClick={handleConfirm}
          autoFocus
          aria-describedby={messageId}
        >
          {confirmText}
        </Button>
      </div>
    </Modal>
  );
};

export default ConfirmDialog;

