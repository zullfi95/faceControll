import toast from 'react-hot-toast';

export const showToast = {
  success: (message) => {
    toast.success(message, {
      duration: 4000,
      style: {
        background: '#ECFDF5',
        color: '#059669',
        border: '1px solid #10B981',
      },
      iconTheme: {
        primary: '#059669',
        secondary: '#ECFDF5',
      },
    });
  },
  
  error: (message) => {
    toast.error(message, {
      duration: 5000,
      style: {
        background: '#FEF2F2',
        color: '#DC2626',
        border: '1px solid #EF4444',
      },
      iconTheme: {
        primary: '#DC2626',
        secondary: '#FEF2F2',
      },
    });
  },
  
  warning: (message) => {
    toast(message, {
      duration: 4000,
      icon: '⚠️',
      style: {
        background: '#FFFBEB',
        color: '#D97706',
        border: '1px solid #F59E0B',
      },
    });
  },
  
  info: (message) => {
    toast(message, {
      duration: 4000,
      icon: 'ℹ️',
      style: {
        background: '#EFF6FF',
        color: '#2563EB',
        border: '1px solid #3B82F6',
      },
    });
  },
};

export default showToast;

