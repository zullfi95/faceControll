import React from 'react';

const Input = ({
  label,
  error,
  helperText,
  required = false,
  className = '',
  id: inputId,
  ...props
}) => {
  const id = inputId || `input-${Math.random().toString(36).substr(2, 9)}`;
  const errorId = error ? `${id}-error` : undefined;
  const helperId = helperText && !error ? `${id}-helper` : undefined;

  return (
    <div className="w-full">
      {label && (
        <label
          htmlFor={id}
          className="block text-sm font-medium text-gray-700 mb-1.5"
        >
          {label}
          {required && <span className="text-red-500 ml-1" aria-label="обязательное поле">*</span>}
        </label>
      )}
      <input
        id={id}
        className={`
          block w-full rounded-md border-gray-300 shadow-sm
          focus:border-[rgb(19,91,147)] focus:ring-[rgb(19,91,147)]
          sm:text-sm transition-colors duration-200
          ${error ? 'border-red-300 focus:border-red-500 focus:ring-red-500' : ''}
          ${props.disabled ? 'bg-gray-100 cursor-not-allowed' : 'bg-white'}
          ${className}
        `}
        aria-invalid={error ? 'true' : 'false'}
        aria-describedby={errorId || helperId}
        aria-required={required}
        {...props}
      />
      {error && (
        <p id={errorId} className="mt-1.5 text-sm text-red-600" role="alert">
          {error}
        </p>
      )}
      {helperText && !error && (
        <p id={helperId} className="mt-1.5 text-sm text-gray-500">
          {helperText}
        </p>
      )}
    </div>
  );
};

export default Input;

