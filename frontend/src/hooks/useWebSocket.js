import { useEffect, useRef, useState, useCallback, useMemo } from 'react';

export const useWebSocket = (url, options = {}) => {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const [error, setError] = useState(null);
  
  // Используем ref для хранения текущего состояния WebSocket
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  
  // Извлекаем опции с дефолтными значениями
  const {
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    reconnectInterval = 5000,
    maxReconnectAttempts = 5,
    enabled = true
  } = options;

  // Сохраняем коллбеки в ref, чтобы они всегда были актуальными без перезапуска эффекта
  const onMessageRef = useRef(onMessage);
  const onConnectRef = useRef(onConnect);
  const onDisconnectRef = useRef(onDisconnect);
  const onErrorRef = useRef(onError);

  useEffect(() => { onMessageRef.current = onMessage; }, [onMessage]);
  useEffect(() => { onConnectRef.current = onConnect; }, [onConnect]);
  useEffect(() => { onDisconnectRef.current = onDisconnect; }, [onDisconnect]);
  useEffect(() => { onErrorRef.current = onError; }, [onError]);

  // Основная функция подключения
  const connect = useCallback(() => {
    // Если выключено или уже есть активное соединение, выходим
    if (!enabled) return;
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    // Лимит попыток
    if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
      return;
    }

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        // Проверяем, что это всё ещё актуальное соединение
        if (wsRef.current !== ws) {
          ws.close();
          return;
        }
        
        setIsConnected(true);
        setError(null);
        reconnectAttemptsRef.current = 0;
        
        // Опционально: уведомление о подключении
        onConnectRef.current?.();
      };

      ws.onmessage = (event) => {
        if (wsRef.current !== ws) return;
        
        try {
          const message = JSON.parse(event.data);
          
          // Обработка пинга для поддержания активности
          if (message.type === 'ping') {
            if (ws.readyState === WebSocket.OPEN) {
              try { ws.send(JSON.stringify({ type: 'pong' })); } catch (e) {}
            }
            return;
          }
          
          if (message.type === 'connected') return;
          
          setLastMessage(message);
          onMessageRef.current?.(message);
        } catch (err) {
          console.error('[useWebSocket] Error parsing message:', err);
        }
      };

      ws.onclose = (event) => {
        // Если это было наше текущее соединение, сбрасываем состояние
        if (wsRef.current === ws) {
          wsRef.current = null;
          setIsConnected(false);
        }
        
        onDisconnectRef.current?.(event);

        // Переподключение при ошибке (не код 1000 или 1001)
        if (enabled && event.code !== 1000 && event.code !== 1001 && reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current += 1;
          
          if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, reconnectInterval);
        }
      };

      ws.onerror = (event) => {
        if (wsRef.current !== ws) return;
        setError(event);
        onErrorRef.current?.(event);
        // Не логируем в консоль браузера ошибку подключения, она будет в onclose
      };

    } catch (err) {
      console.error('[useWebSocket] Setup error:', err);
      if (enabled && reconnectAttemptsRef.current < maxReconnectAttempts) {
        reconnectAttemptsRef.current += 1;
        reconnectTimeoutRef.current = setTimeout(connect, reconnectInterval);
      }
    }
  }, [url, enabled, reconnectInterval, maxReconnectAttempts]);

  // Функция принудительного отключения
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      const ws = wsRef.current;
      wsRef.current = null;
      // Закрываем только если не в процессе закрытия/закрыто
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close(1000, "Normal closure");
      }
    }

    setIsConnected(false);
  }, []);

  const send = useCallback((data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
      return true;
    }
    return false;
  }, []);

  // Управление жизненным циклом через useEffect
  useEffect(() => {
    if (enabled) {
      connect();
    } else {
      disconnect();
    }

    return () => {
      // При размонтировании или смене зависимостей
      disconnect();
    };
  }, [enabled, connect, disconnect]); // connect и disconnect зависят только от url и базовых опций

  return { isConnected, lastMessage, error, send, connect, disconnect };
};

// Специализированные хуки
export const useEventsWebSocket = (options = {}) => {
  const wsUrl = useMemo(() => 
    `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/ws/events`,
    []
  );
  return useWebSocket(wsUrl, options);
};

export const useReportsWebSocket = (options = {}) => {
  const wsUrl = useMemo(() => 
    `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/ws/reports`,
    []
  );
  return useWebSocket(wsUrl, options);
};

export const useDashboardWebSocket = (options = {}) => {
  const wsUrl = useMemo(() => 
    `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/ws/dashboard`,
    []
  );
  return useWebSocket(wsUrl, options);
};
