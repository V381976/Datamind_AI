'use client';

import { useEffect, useRef, useState } from 'react';
import { ChatInput } from '@/components/ChatInput';
import { ChatMessage } from '@/components/ChatMessage';
import { ChatHistory } from '@/components/ChatHistory';
import { Header } from '@/components/Header';
import { LoadingMessage } from '@/components/LoadingMessage';
import {
  clearConversationId,
  fetchChatHistory,
  fetchConversations,
  getConversationId,
  sendChatMessage,
  setConversationId,
} from '@/lib/api';
import { ChatMessage as ChatMessageType, Conversation } from '@/types/chat';

const starterMessage: ChatMessageType = {
  id: 'welcome',
  role: 'assistant',
  content:
    'Welcome! Ask me about trading (stocks, forex, crypto, options), technical analysis, risk management, or query your PostgreSQL database.',
  timestamp: '',
};

export default function HomePage() {
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationIdState] = useState<string | null>(null);
  const [historyReady, setHistoryReady] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);

  const loadConversations = async () => {
    try {
      const data = await fetchConversations();
      setConversations(data.conversations);
      setErrorMessage(null);
    } catch {
      setErrorMessage('Could not load conversation history. Check that the backend is running.');
    }
  };

  useEffect(() => {
    let cancelled = false;

    const loadHistory = async () => {
      const existingId = getConversationId();
      if (!existingId) {
        if (!cancelled) {
          setMessages([
            {
              ...starterMessage,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            },
          ]);
          setHistoryReady(true);
        }
        return;
      }

      try {
        const history = await fetchChatHistory(existingId);
        if (cancelled) {
          return;
        }
        setConversationIdState(existingId);
        if (history.messages.length > 0) {
          setMessages(
            history.messages.map((item) => ({
              id: item.id,
              role: item.role,
              content: item.content,
              timestamp: item.timestamp,
              tool: item.tool,
              table: item.table,
              plan: item.plan,
              result: item.result,
            })),
          );
        } else {
          setMessages([
            {
              ...starterMessage,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            },
          ]);
        }
        setErrorMessage(null);
      } catch {
        if (!cancelled) {
          clearConversationId();
          setMessages([
            {
              ...starterMessage,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            },
          ]);
          setErrorMessage('Previous conversation could not be loaded. Starting a fresh chat.');
        }
      } finally {
        if (!cancelled) {
          setHistoryReady(true);
        }
      }
    };

    void loadHistory();
    void loadConversations();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const startNewChat = () => {
    clearConversationId();
    setConversationIdState(null);
    setMessages([
      {
        ...starterMessage,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
    void loadConversations();
  };

  const selectConversation = async (id: string) => {
    clearConversationId();
    setConversationIdState(id);
    setConversationId(id);
    setHistoryReady(false);
    try {
      const history = await fetchChatHistory(id);
      if (history.messages.length > 0) {
        setMessages(
          history.messages.map((item) => ({
            id: item.id,
            role: item.role,
            content: item.content,
            timestamp: item.timestamp,
            tool: item.tool,
            table: item.table,
            plan: item.plan,
            result: item.result,
          })),
        );
      } else {
        setMessages([
          {
            ...starterMessage,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
      }
      setErrorMessage(null);
    } catch {
      setMessages([
        {
          ...starterMessage,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
      setErrorMessage('Could not open that conversation.');
    } finally {
      setHistoryReady(true);
      void loadConversations();
    }
  };

  const sendMessage = async () => {
    const trimmedInput = input.trim();
    if (!trimmedInput || isLoading) {
      return;
    }

    const userMessage: ChatMessageType = {
      id: crypto.randomUUID(),
      role: 'user',
      content: trimmedInput,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((current) => [...current, userMessage]);
    setInput('');
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const response = await sendChatMessage(trimmedInput, conversationId);
      if (response.conversation_id) {
        setConversationId(response.conversation_id);
        setConversationIdState(response.conversation_id);
      }
      const assistantMessage: ChatMessageType = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: response.answer || 'Sorry, I could not process that request. Please try again.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        tool: response.tool,
        table: response.table,
        plan: response.plan,
        result: response.result,
      };
      setMessages((current) => [...current, assistantMessage]);
    } catch {
      setErrorMessage('Message failed. Make sure the backend is running on port 8001.');
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: "Sorry, I couldn't process that request. Please try again.",
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } finally {
      setIsLoading(false);
      void loadConversations();
    }
  };

  return (
    <main className="flex min-h-screen flex-col bg-slate-950 text-slate-50">
      <Header />
      <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-6">
        {errorMessage && (
          <div className="mb-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-200">
            {errorMessage}
          </div>
        )}
        <div className="mb-3 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={() => setSidebarOpen((value) => !value)}
            className="rounded-full border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-200 transition hover:border-sky-500/40"
          >
            {sidebarOpen ? 'Hide history' : 'Show history'}
          </button>
          <button
            type="button"
            onClick={startNewChat}
            className="rounded-full border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-200 transition hover:border-sky-500/40"
          >
            New chat
          </button>
        </div>
        <div className="relative flex min-h-0 flex-1 gap-4">
          {sidebarOpen && (
            <ChatHistory
              conversations={conversations}
              currentConversationId={conversationId}
              onSelectConversation={selectConversation}
              onNewChat={startNewChat}
            />
          )}
          <div className="flex min-h-0 min-w-0 flex-1 flex-col">
            <div
              ref={listRef}
              className="flex-1 space-y-4 overflow-y-auto rounded-2xl border border-slate-800 bg-slate-900/60 p-4 shadow-glow"
            >
              {!historyReady && <LoadingMessage />}
              {historyReady && messages.map((message) => <ChatMessage key={message.id} message={message} />)}
              {isLoading && <LoadingMessage />}
            </div>
            <div className="pt-3">
              <ChatInput value={input} onChange={setInput} onSend={sendMessage} disabled={isLoading || !historyReady} />
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
