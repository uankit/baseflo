import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { Insight } from '@baseflo/contracts';

export function useInsightWebSocket(projectId: string | null) {
  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!projectId) return;

    const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/insights/${projectId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      // connected
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'insight' && msg.payload) {
          const newInsight = msg.payload as Insight;
          // Prepend to existing list
          queryClient.setQueryData(['insights', projectId], (old: { items: Insight[]; total: number; unread_count: number } | undefined) => {
            if (!old) return old;
            return {
              ...old,
              items: [newInsight, ...old.items],
              total: old.total + 1,
              unread_count: old.unread_count + 1,
            };
          });
        }
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      // disconnected
    };

    ws.onerror = (err) => {
      console.error('[WS] error', err);
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [projectId, queryClient]);

  return wsRef;
}
