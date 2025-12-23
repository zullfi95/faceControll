import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './contexts/AuthContext'
import { Toaster } from 'react-hot-toast'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000, // Данные считаются устаревшими через 30 секунд
      gcTime: 24 * 60 * 60 * 1000, // 24 часа - время хранения в кеше
      refetchOnWindowFocus: true, // Перезагружать при фокусе окна для актуальности
      refetchOnMount: true, // Перезагружать при монтировании для свежих данных
      refetchOnReconnect: true, // Перезагружать при переподключении
      retry: 1, // Количество повторных попыток
      structuralSharing: true, // Использовать структурное разделение для оптимизации
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')).render(
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <App />
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            borderRadius: '8px',
            padding: '12px 16px',
          },
        }}
      />
    </AuthProvider>
  </QueryClientProvider>
)

