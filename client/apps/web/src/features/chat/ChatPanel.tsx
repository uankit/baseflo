import React, { useState } from 'react';
import { useChat } from './useChat.js';

export function ChatPanel() {
  const { messages, sendMessage, isLoading } = useChat();
  const [input, setInput] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    sendMessage(input.trim());
    setInput('');
  };

  return (
    <div className="flex h-full flex-col border-l border-gray-800 bg-gray-950">
      <div className="flex h-14 items-center border-b border-gray-800 px-4">
        <h3 className="text-sm font-medium text-gray-200">Ask about your data</h3>
      </div>

      <div className="flex-1 overflow-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-xs text-gray-600 mt-8">
            Ask a question about your data and the brain will answer.
          </div>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] rounded-lg px-3 py-2 text-xs ${
                msg.role === 'user'
                  ? 'bg-gray-800 text-gray-100'
                  : 'bg-gray-900 text-gray-300'
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>
              {typeof msg.toolCalls === 'number' && msg.toolCalls > 0 && (
                <div className="mt-2 border-t border-gray-800 pt-2 text-[10px] uppercase tracking-[0.12em] text-gray-600">
                  {msg.toolCalls} tool calls
                </div>
              )}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex justify-start">
            <div className="rounded-lg bg-gray-900 px-3 py-2 text-xs text-gray-500">
              Thinking…
            </div>
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="border-t border-gray-800 p-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask anything…"
            className="flex-1 rounded-lg border border-gray-800 bg-gray-900 px-3 py-2 text-xs text-white placeholder-gray-600 outline-none focus:border-gray-600"
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="rounded-lg bg-white px-3 py-2 text-xs font-medium text-gray-950 hover:bg-gray-100 disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
}
