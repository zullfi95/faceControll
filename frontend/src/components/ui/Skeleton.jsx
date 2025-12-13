import React from 'react';

const Skeleton = ({
  className = '',
  variant = 'text',
  width,
  height,
  'aria-label': ariaLabel = 'Загрузка...',
  ...props
}) => {
  const baseStyles = 'animate-pulse bg-gray-200 rounded';
  
  const variants = {
    text: 'h-4',
    circular: 'rounded-full',
    rectangular: '',
  };
  
  const style = {
    ...(width && { width }),
    ...(height && { height }),
  };
  
  return (
    <div
      className={`${baseStyles} ${variants[variant]} ${className}`}
      style={style}
      role="presentation"
      aria-label={ariaLabel}
      {...props}
    />
  );
};

export default Skeleton;

