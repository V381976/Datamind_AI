import { ChatResponse, HistoryResponse, ConversationsResponse } from '@/types/chat';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001';
const CONVERSATION_KEY = 'my_basic_llm_conversation_id';

export type ModelStatus = {
  status: string;
  llm: string;
  custom_llm_ready: boolean;
  database: {
    connected?: boolean;
    database_type?: string;
    database_name?: string;
    host?: string;
    url_present?: boolean;
  };
  embedding?: Record<string, unknown>;
  qdrant?: Record<string, unknown>;
};

export function getConversationId(): string | null {
  if (typeof window === 'undefined') {
    return null;
  }
  return window.localStorage.getItem(CONVERSATION_KEY);
}

export function setConversationId(conversationId: string): void {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.setItem(CONVERSATION_KEY, conversationId);
}

export function clearConversationId(): void {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.removeItem(CONVERSATION_KEY);
}

export async function fetchModelStatus(): Promise<ModelStatus> {
  const response = await fetch(`${API_URL}/model-status`);
  if (!response.ok) {
    throw new Error(`Status request failed with status ${response.status}`);
  }
  return (await response.json()) as ModelStatus;
}

export async function sendChatMessage(message: string, conversationId?: string | null): Promise<ChatResponse> {
  const response = await fetch(`${API_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      conversation_id: conversationId || undefined,
    }),
  });

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }

  const data = (await response.json()) as ChatResponse;
  if (!data || typeof data.answer !== 'string' || !data.answer.trim()) {
    throw new Error('Empty response from backend');
  }

  return data;
}

export async function fetchChatHistory(conversationId: string): Promise<HistoryResponse> {
  const response = await fetch(`${API_URL}/chat/history?conversation_id=${encodeURIComponent(conversationId)}`);
  if (!response.ok) {
    throw new Error(`History request failed with status ${response.status}`);
  }
  return (await response.json()) as HistoryResponse;
}

export async function fetchConversations(): Promise<ConversationsResponse> {
  const response = await fetch(`${API_URL}/chat/conversations?limit=50`);
  if (!response.ok) {
    throw new Error(`Conversations request failed with status ${response.status}`);
  }
  return (await response.json()) as ConversationsResponse;
}
