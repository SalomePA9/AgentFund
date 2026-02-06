'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useChat } from '@/hooks/useChat';
import { useAgent } from '@/hooks/useAgents';
import { PageLoading, ErrorMessage, LoadingSpinner } from '@/components/ui';
import { formatDate } from '@/lib/utils';
import type { ChatMessage } from '@/types';

export default function AgentChatPage() {
  const params = useParams();
  const agentId = params.id as string;
  const { agent, isLoading: agentLoading, error: agentError } = useAgent(agentId);
  const {
    messages,
    isLoading: chatLoading,
    isSending,
    hasMore,
    error,
    sendMessage,
    loadMore,
    clearHistory,
  } = useChat(agentId);

  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const prevMessageCountRef = useRef(0);

  // Auto-scroll to bottom only on new messages (not on loadMore which prepends)
  useEffect(() => {
    const isNewMessage = messages.length > prevMessageCountRef.current;
    const lastMessage = messages[messages.length - 1];
    const isRecentMessage = lastMessage && !lastMessage.id.startsWith('older-');

    if (isNewMessage && isRecentMessage && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
    prevMessageCountRef.current = messages.length;
  }, [messages]);

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || isSending) return;

    setInput('');
    await sendMessage(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (agentLoading || chatLoading) return <PageLoading />;
  if (agentError) return <ErrorMessage message={agentError} />;

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      {/* Chat Header */}
      <div className="flex items-center justify-between pb-4 border-b border-border">
        <div className="flex items-center gap-3">
          <Link
            href={`/agents/${agentId}`}
            className="text-zinc-400 hover:text-zinc-50"
          >
            &larr;
          </Link>
          <div className="w-10 h-10 rounded-full bg-accent/20 flex items-center justify-center text-accent font-bold">
            {agent?.name?.charAt(0) ?? 'A'}
          </div>
          <div>
            <h1 className="font-semibold">{agent?.name ?? 'Agent'}</h1>
            <p className="text-xs text-zinc-500 capitalize">
              {agent?.persona ?? ''} · {agent?.strategy_type?.replace(/_/g, ' ') ?? ''}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={clearHistory}
            className="btn btn-ghost text-xs"
            title="Clear chat history"
          >
            Clear
          </button>
        </div>
      </div>

      {error && (
        <div className="px-4 py-2">
          <ErrorMessage message={error} />
        </div>
      )}

      {/* Messages */}
      <div
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto py-4 space-y-4 scrollbar-hide"
      >
        {/* Load More */}
        {hasMore && (
          <div className="text-center">
            <button onClick={loadMore} className="btn btn-ghost text-xs">
              Load earlier messages
            </button>
          </div>
        )}

        {messages.length === 0 && !isSending && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-16 h-16 rounded-full bg-accent/10 flex items-center justify-center text-accent text-2xl font-bold mb-4">
              {agent?.name?.charAt(0) ?? 'A'}
            </div>
            <h3 className="text-lg font-medium">Chat with {agent?.name ?? 'your agent'}</h3>
            <p className="text-sm text-zinc-400 mt-1 max-w-md">
              Ask about market conditions, trading decisions, portfolio strategy,
              or anything else.
            </p>
            <div className="flex gap-2 mt-4 flex-wrap justify-center">
              {quickPrompts.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => { setInput(''); sendMessage(prompt); }}
                  className="btn btn-secondary text-xs py-1.5"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} agentName={agent?.name ?? 'Agent'} />
        ))}

        {/* Typing indicator */}
        {isSending && (
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center text-accent text-xs font-bold flex-shrink-0">
              {agent?.name?.charAt(0) ?? 'A'}
            </div>
            <div className="card py-3 px-4">
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 bg-zinc-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 bg-zinc-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 bg-zinc-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="pt-4 border-t border-border">
        <div className="flex items-end gap-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Message ${agent?.name ?? 'agent'}...`}
            className="input resize-none min-h-[44px] max-h-32"
            rows={1}
            disabled={isSending}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isSending}
            className="btn btn-primary px-4 py-3"
          >
            {isSending ? (
              <LoadingSpinner size="sm" />
            ) : (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                />
              </svg>
            )}
          </button>
        </div>
        <p className="text-xs text-zinc-500 mt-2 text-center">
          Press Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}

function MessageBubble({
  message,
  agentName,
}: {
  message: ChatMessage;
  agentName: string;
}) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex items-start gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 ${
          isUser
            ? 'bg-zinc-600 text-zinc-200'
            : 'bg-accent/20 text-accent'
        }`}
      >
        {isUser ? 'You' : agentName.charAt(0)}
      </div>

      {/* Message */}
      <div
        className={`max-w-[75%] rounded-xl px-4 py-3 ${
          isUser
            ? 'bg-accent text-white'
            : 'bg-background-secondary border border-border'
        }`}
      >
        <div className="text-sm whitespace-pre-wrap leading-relaxed">
          {message.message}
        </div>
        <div
          className={`text-xs mt-2 ${
            isUser ? 'text-blue-200' : 'text-zinc-500'
          }`}
        >
          {formatDate(message.created_at, { format: 'relative' })}
        </div>
      </div>
    </div>
  );
}

const quickPrompts = [
  "How's the portfolio doing?",
  'What trades are you considering?',
  'Explain your current positions',
  'What risks should I watch?',
];
