'use client';

import { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react';
import {
  clearConversationId,
  fetchChatHistory,
  fetchConversations,
  getConversationId,
  sendChatMessage,
  setConversationId,
} from '@/lib/api';

// Types
export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  sources?: { title: string; url: string; source: string }[] | null;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Settings {
  temperature: number;
  maxTokens: number;
  systemPrompt: string;
  model: string;
  fontSize: 'small' | 'medium' | 'large';
  sendOnEnter: boolean;
  showTimestamps: boolean;
  compactMode: boolean;
}

export interface ChatContextType {
  // Theme
  theme: 'dark' | 'light';
  toggleTheme: () => void;

  // Conversations
  conversations: Conversation[];
  currentConversationId: string | null;
  selectConversation: (id: string) => Promise<void>;
  createNewChat: () => void;
  deleteConversation: (id: string) => Promise<void>;
  renameConversation: (id: string, title: string) => void;

  // Messages
  messages: Message[];
  isLoading: boolean;
  error: string | null;
  sendMessage: (content: string) => Promise<void>;
  stopGeneration: () => void;

  // Settings
  settings: Settings;
  updateSettings: (settings: Partial<Settings>) => void;
  showSettings: boolean;
  setShowSettings: (show: boolean) => void;

  // Sidebar
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;

  // Chat title (editable)
  chatTitle: string;
  setChatTitle: (title: string) => void;
}

const defaultSettings: Settings = {
  temperature: 0.7,
  maxTokens: 2000,
  systemPrompt: 'You are a helpful AI assistant. You can help with questions about technology, AI, programming, trading, general knowledge, and almost any topic.',
  model: 'MyModel-v1',
  fontSize: 'medium',
  sendOnEnter: true,
  showTimestamps: true,
  compactMode: false,
};

// Load from localStorage with fallback
function loadFromStorage<T>(key: string, fallback: T): T {
  if (typeof window === 'undefined') return fallback;
  try {
    const stored = localStorage.getItem(key);
    if (stored !== null) {
      return JSON.parse(stored) as T;
    }
  } catch {}
  return fallback;
}

function saveToStorage(key: string, value: unknown) {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {}
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

export function ChatProvider({ children }: { children: ReactNode }) {
  // Theme state - persisted to localStorage
  const [theme, setTheme] = useState<'dark' | 'light'>(() => 
    loadFromStorage<'dark' | 'light'>('datamind_theme', 'dark')
  );

  // Sidebar state
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Conversations state
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [chatTitle, setChatTitle] = useState('New Chat');

  // Messages state
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [abortController, setAbortController] = useState<AbortController | null>(null);

  // Settings state - persisted to localStorage
  const [settings, setSettings] = useState<Settings>(() =>
    loadFromStorage<Settings>('datamind_settings', defaultSettings)
  );
  const [showSettings, setShowSettings] = useState(false);

  // Apply theme to html element and persist
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    document.documentElement.classList.toggle('light', theme === 'light');
    saveToStorage('datamind_theme', theme);
  }, [theme]);

  // Persist settings to localStorage
  useEffect(() => {
    saveToStorage('datamind_settings', settings);
  }, [settings]);

  // Load conversations on mount
  useEffect(() => {
    loadConversations();
  }, []);

  const loadConversations = async () => {
    try {
      const data = await fetchConversations();
      setConversations(data.conversations.map(c => ({
        id: c.id,
        title: c.first_question || 'New Chat',
        created_at: c.created_at,
        updated_at: c.updated_at,
      })));
    } catch {
      // Backend might not be running
    }
  };

  const toggleTheme = useCallback(() => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  }, []);

  const createNewChat = useCallback(() => {
    clearConversationId();
    setCurrentConversationId(null);
    setMessages([]);
    setChatTitle('New Chat');
    setError(null);
    void loadConversations();
  }, []);

  const selectConversation = useCallback(async (id: string) => {
    clearConversationId();
    setCurrentConversationId(id);
    setConversationId(id);
    setIsLoading(true);
    setError(null);

    try {
      const history = await fetchChatHistory(id);
      if (history.messages.length > 0) {
        setMessages(history.messages.map(item => ({
          id: item.id,
          role: item.role,
          content: item.content,
          timestamp: item.timestamp,
          sources: (item as any).sources ?? null,
        })));
        const firstUserMsg = history.messages.find(m => m.role === 'user');
        setChatTitle(firstUserMsg?.content?.slice(0, 30) || 'Chat');
      } else {
        setMessages([]);
        setChatTitle('New Chat');
      }
    } catch {
      setMessages([]);
      setChatTitle('New Chat');
      setError('Could not load conversation.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const deleteConversation = useCallback(async (id: string) => {
    setConversations(prev => prev.filter(c => c.id !== id));
    if (currentConversationId === id) {
      createNewChat();
    }
  }, [currentConversationId, createNewChat]);

  const renameConversation = useCallback((id: string, title: string) => {
    setConversations(prev =>
      prev.map(c => c.id === id ? { ...c, title } : c)
    );
  }, []);

  const updateSettings = useCallback((newSettings: Partial<Settings>) => {
    setSettings(prev => ({ ...prev, ...newSettings }));
  }, []);

  const stopGeneration = useCallback(() => {
    if (abortController) {
      abortController.abort();
      setAbortController(null);
      setIsLoading(false);
    }
  }, [abortController]);

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isLoading) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: content.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);
    setError(null);

    if (messages.length === 0) {
      setChatTitle(content.slice(0, 30));
    }

    const controller = new AbortController();
    setAbortController(controller);

    try {
      const response = await sendChatMessage(content, currentConversationId);

      if (response.conversation_id) {
        setCurrentConversationId(response.conversation_id);
        setConversationId(response.conversation_id);
      }

      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: response.answer || 'Sorry, I could not process that request.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        sources: response.sources ?? undefined,
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        setError('Message failed. Please try again.');
        setMessages(prev => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: "Sorry, I couldn't process that request. Please try again.",
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
      }
    } finally {
      setIsLoading(false);
      setAbortController(null);
      void loadConversations();
    }
  }, [isLoading, messages.length, currentConversationId]);

  return (
    <ChatContext.Provider
      value={{
        theme,
        toggleTheme,
        conversations,
        currentConversationId,
        selectConversation,
        createNewChat,
        deleteConversation,
        renameConversation,
        messages,
        isLoading,
        error,
        sendMessage,
        stopGeneration,
        settings,
        updateSettings,
        showSettings,
        setShowSettings,
        sidebarOpen,
        setSidebarOpen,
        chatTitle,
        setChatTitle,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
}
