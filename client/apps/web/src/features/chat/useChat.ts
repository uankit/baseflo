import { useState, useCallback } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useGateway } from '../../providers/GatewayProvider.js';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: number;
  artifacts?: Array<Record<string, unknown>>;
}

export function useChat() {
  const gateway = useGateway();
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const askMutation = useMutation({
    mutationFn: (question: string) => gateway.query.ask({ question }),
  });

  const sendMessage = useCallback(
    async (content: string) => {
      const userMsg: ChatMessage = {
        id: Math.random().toString(36).slice(2),
        role: 'user',
        content,
      };
      setMessages((prev) => [...prev, userMsg]);

      try {
        const resp = await askMutation.mutateAsync(content);
        const assistantMsg: ChatMessage = {
          id: Math.random().toString(36).slice(2),
          role: 'assistant',
          content: resp.answer,
          toolCalls: resp.tool_calls.length,
          artifacts: resp.artifacts,
        };
        setMessages((prev) => [...prev, assistantMsg]);
      } catch (err) {
        const errorMsg: ChatMessage = {
          id: Math.random().toString(36).slice(2),
          role: 'assistant',
          content: err instanceof Error ? err.message : 'Something went wrong.',
        };
        setMessages((prev) => [...prev, errorMsg]);
      }
    },
    [askMutation],
  );

  return {
    messages,
    sendMessage,
    isLoading: askMutation.isPending,
  };
}
