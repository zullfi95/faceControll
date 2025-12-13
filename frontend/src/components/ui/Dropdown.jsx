import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const Dropdown = ({
  trigger,
  children,
  align = 'right',
  className = '',
  'aria-label': ariaLabel,
  'aria-expanded': ariaExpanded,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);
  
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);
  
  const alignClasses = {
    left: 'left-0',
    right: 'right-0',
    center: 'left-1/2 transform -translate-x-1/2',
  };
  
  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      <div
        onClick={() => setIsOpen(!isOpen)}
        role="button"
        tabIndex={0}
        aria-label={ariaLabel}
        aria-expanded={ariaExpanded !== undefined ? ariaExpanded : isOpen}
        aria-haspopup="menu"
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            setIsOpen(!isOpen);
          } else if (e.key === 'Escape' && isOpen) {
            setIsOpen(false);
          }
        }}
      >
        {trigger}
      </div>
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -10 }}
            transition={{ duration: 0.15 }}
            className={`
              absolute z-50 mt-2 w-56 rounded-md shadow-large
              bg-white border border-gray-200 py-1
              ${alignClasses[align]}
            `}
            role="menu"
            aria-label="Меню"
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export const DropdownItem = ({
  children,
  onClick,
  icon: Icon,
  danger = false,
  className = '',
  ...props
}) => {
  return (
    <button
      onClick={onClick}
      role="menuitem"
      className={`
        w-full text-left px-4 py-2 text-sm flex items-center gap-2
        transition-colors duration-150 focus:outline-none focus:bg-gray-100
        ${danger
          ? 'text-red-600 hover:bg-red-50 focus:bg-red-50'
          : 'text-gray-700 hover:bg-gray-100 focus:bg-gray-100'
        }
        ${className}
      `}
      {...props}
    >
      {Icon && <Icon className="h-4 w-4" aria-hidden="true" />}
      {children}
    </button>
  );
};

export const DropdownDivider = () => {
  return <div className="border-t border-gray-200 my-1" />;
};

export default Dropdown;

