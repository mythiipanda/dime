import { useState, useEffect, useRef, useCallback } from 'react';
import { ScoreboardData } from '@/app/(app)/games/types'; 
import { API_BASE_URL } from '@/lib/config';

interface UseScoreboardWebSocketOptions {
  viewingToday: boolean;
  onDataReceived: (data: ScoreboardData) => void;
  onLoadingChange: (isLoading: boolean) => void;
  onErrorChange: (error: string | null) => void;
  onConnectionChange: (isConnected: boolean) => void;
}

export function useScoreboardWebSocket({
  viewingToday,
  onDataReceived,
  onLoadingChange,
  onErrorChange,
  onConnectionChange,
}: UseScoreboardWebSocketOptions) {
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!viewingToday) {
      if (ws.current) {
        console.log("[WebSocket Hook] Not viewing today, closing connection.");
        ws.current.close(1000, "Navigated off today");
        ws.current = null;
        onConnectionChange(false);
      }
      return;
    }

    if (!ws.current) {
      const wsBaseUrl = API_BASE_URL.replace(/^http(s?):/, 'ws:');
      const wsUrl = `${wsBaseUrl}/scoreboard/ws`;

      console.log("[WebSocket Hook] Attempting to connect to:", wsUrl);
      const socket = new WebSocket(wsUrl);
      ws.current = socket;
      onLoadingChange(true); // Signal loading when attempting to connect

      socket.onopen = () => {
        console.log("[WebSocket Hook] Connection established");
        onConnectionChange(true);
        onErrorChange(null);
        onLoadingChange(false);
      };

      socket.onclose = (event) => {
        console.log(`[WebSocket Hook] Connection closed: ${event.code} - ${event.reason}`);
        if (ws.current === socket) {
          ws.current = null;
          onConnectionChange(false);
          if (viewingToday && event.code !== 1000 && event.code !== 1005) { // 1000 = Normal Closure, 1005 = No Status Rcvd
            onErrorChange("WebSocket connection lost.");
          }
          onLoadingChange(false); // Stop loading on close if it was trying to connect
        }
      };

      socket.onerror = (ev) => {
        console.error("[WebSocket Hook] Error:", ev);
        if (ws.current === socket) {
          onErrorChange("WebSocket connection error.");
          onConnectionChange(false);
          onLoadingChange(false);
          ws.current = null;
        }
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data && typeof data === 'object' && Array.isArray(data.games)) {
            onDataReceived(data as ScoreboardData);
            onErrorChange(null); // Clear error on successful message
            onLoadingChange(false); // Data received, no longer "initial" loading via WS
          } else {
            console.warn("[WebSocket Hook] Received invalid data structure:", data);
            // Optionally set an error if malformed data is critical
            // onErrorChange("Received malformed data from WebSocket.");
          }
        } catch (parseError) {
          console.error("[WebSocket Hook] Failed to parse message data:", parseError, "Raw:", event.data);
          onErrorChange("Failed to parse WebSocket message.");
        }
      };
    }

    // Cleanup function
    return () => {
      if (ws.current && ws.current.readyState === WebSocket.OPEN) {
        console.log("[WebSocket Hook Cleanup] Closing connection");
        ws.current.close(1000, "Hook cleanup");
      }
    };
  }, [viewingToday, API_BASE_URL, onDataReceived, onLoadingChange, onErrorChange, onConnectionChange]);

  // Expose a way to manually close the WebSocket if needed, though cleanup effect should handle most cases
  const closeWebSocket = useCallback(() => {
    if (ws.current) {
      console.log("[WebSocket Hook] Manually closing WebSocket.");
      ws.current.close(1000, "Manual close");
      ws.current = null;
      onConnectionChange(false);
    }
  }, [onConnectionChange]);

  return { closeWebSocket };
} 