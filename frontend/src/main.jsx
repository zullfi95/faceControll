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
      staleTime: Infinity, // Данные никогда не считаются устаревшими (пока не инвалидированы вручную)
      gcTime: 24 * 60 * 60 * 1000, // 24 часа - время хранения в кеше
      refetchOnWindowFocus: false, // Не перезагружать при фокусе окна
      refetchOnMount: false, // Не перезагружать при монтировании, если данные есть в кеше
      refetchOnReconnect: false, // Не перезагружать при переподключении
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

