import { useEffect, useRef, useState, useCallback } from 'react';

export const useWebSocket = (url, options = {}) => {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const [error, setError] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttempts = useRef(0);

  const {
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    reconnectInterval = 10000,
    maxReconnectAttempts = 3,
    enabled = true
  } = options;

  const connect = useCallback(() => {
    if (!enabled || wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    // Не пытаемся подключиться, если уже достигли лимита попыток
    if (reconnectAttempts.current > maxReconnectAttempts) {
      return;
    }

    try {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        setIsConnected(true);
        setError(null);
        reconnectAttempts.current = 0;
        
        // Отправляем начальное сообщение для подтверждения готовности
        try {
          ws.send(JSON.stringify({ type: 'connected' }));
        } catch (e) {
          // Тихая обработка ошибки
        }
        
        onConnect?.();
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          
          // Игнорируем ping сообщения (они используются для поддержания соединения)
          if (message.type === 'ping') {
            // Отправляем pong в ответ на ping для поддержания соединения
            if (wsRef.current?.readyState === WebSocket.OPEN) {
              try {
                wsRef.current.send(JSON.stringify({ type: 'pong' }));
              } catch (e) {
                // Тихая обработка ошибки
              }
            }
            return;
          }
          
          // Игнорируем служебные сообщения connected
          if (message.type === 'connected') {
            return;
          }
          
          setLastMessage(message);
          onMessage?.(message);
        } catch (err) {
          // Тихая обработка ошибок парсинга
        }
      };

      ws.onclose = (event) => {
        setIsConnected(false);
        onDisconnect?.(event);

        // Попытка переподключения только если соединение было закрыто неожиданно
        // Код 1000 = нормальное закрытие, 1001 = уход со страницы, не переподключаемся
        if (enabled && event.code !== 1000 && event.code !== 1001 && reconnectAttempts.current < maxReconnectAttempts) {
          reconnectAttempts.current += 1;
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, reconnectInterval);
        } else if (reconnectAttempts.current >= maxReconnectAttempts) {
          reconnectAttempts.current = maxReconnectAttempts + 1;
        }
      };

      ws.onerror = (event) => {
        setError(event);
        onError?.(event);
      };

      wsRef.current = ws;
    } catch (err) {
      setError(err);
      
      // Если достигли лимита попыток, не пытаемся больше
      if (reconnectAttempts.current >= maxReconnectAttempts) {
        return;
      }
      
      // Планируем переподключение только если не достигли лимита
      if (enabled && reconnectAttempts.current < maxReconnectAttempts) {
        reconnectAttempts.current += 1;
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, reconnectInterval);
      }
    }
  }, [url, enabled, onConnect, onDisconnect, onError, onMessage, reconnectInterval, maxReconnectAttempts]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
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

  useEffect(() => {
    if (enabled) {
      // Сбрасываем счетчик попыток при включении
      if (reconnectAttempts.current > maxReconnectAttempts) {
        reconnectAttempts.current = 0;
      }
      connect();
    } else {
      disconnect();
      // Сбрасываем счетчик при отключении
      reconnectAttempts.current = 0;
    }

    return () => {
      disconnect();
    };
  }, [enabled, connect, disconnect]);

  return {
    isConnected,
    lastMessage,
    error,
    send,
    connect,
    disconnect
  };
};

// Специализированные хуки для разных каналов
export const useEventsWebSocket = (options = {}) => {
  const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/ws/events`;
  return useWebSocket(wsUrl, options);
};

export const useReportsWebSocket = (options = {}) => {
  const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/ws/reports`;
  return useWebSocket(wsUrl, options);
};

export const useDashboardWebSocket = (options = {}) => {
  const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/ws/dashboard`;
  return useWebSocket(wsUrl, options);
}
