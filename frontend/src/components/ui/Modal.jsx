import React, { useEffect, useRef } from 'react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { motion, AnimatePresence } from 'framer-motion';
import { useFocusTrap, useRestoreFocus } from '../../hooks/useKeyboardNavigation';

const Modal = ({
  isOpen,
  onClose,
  title,
  children,
  footer,
  size = 'md',
  className = '',
  'aria-labelledby': ariaLabelledBy,
  'aria-describedby': ariaDescribedBy,
  triggerRef,
}) => {
  const modalRef = useRef(null);
  
  useFocusTrap(isOpen, modalRef);
  useRestoreFocus(isOpen, triggerRef);

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
  
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);
  
  const sizes = {
    sm: 'max-w-[19.6rem]', // ~313px (было 448px)
    md: 'max-w-[22.4rem]', // ~358px (было 512px)
    lg: 'max-w-[29.4rem]', // ~470px (было 672px)
    xl: 'max-w-[39.2rem]', // ~627px (было 896px)
    full: 'max-w-full mx-4',
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-gray-500 bg-opacity-75"
            onClick={onClose}
          />

          {/* Modal */}
          <div className="fixed inset-0 z-50 overflow-y-auto">
            <div className="flex min-h-full items-center justify-center p-4">
              <motion.div
                ref={modalRef}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.2 }}
                role="dialog"
                aria-modal="true"
                aria-labelledby={ariaLabelledBy || (title ? "modal-title" : undefined)}
                aria-describedby={ariaDescribedBy}
                className={`
                  relative bg-white rounded-lg shadow-large w-full
                  ${sizes[size]}
                  ${className}
                `}
                onClick={(e) => e.stopPropagation()}
              >
          {/* Header */}
          {title && (
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h3
                id={ariaLabelledBy || "modal-title"}
                className="text-lg font-semibold text-gray-900"
              >
                {title}
              </h3>
              <button
                onClick={onClose}
                aria-label="Закрыть модальное окно"
                className="text-gray-400 hover:text-gray-500 transition-colors focus:outline-none focus:ring-2 focus:ring-[rgb(19,91,147)] focus:ring-offset-2 rounded"
              >
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
          )}
          
          {/* Content */}
          <div className={title ? 'px-6 py-4' : 'p-6'}>
            {children}
          </div>
          
          {/* Footer */}
          {footer && (
            <div className="px-6 py-4 border-t border-gray-200 bg-gray-50 rounded-b-lg">
              {footer}
            </div>
          )}
              </motion.div>
            </div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
};

export default Modal;

