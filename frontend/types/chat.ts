export type WebSource = {
  title: string;
  url: string;
  source: string;
};

export type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  tool?: string | null;
  table?: string | null;
  plan?: Record<string, unknown> | null;
  result?: Record<string, unknown> | null;
  sources?: WebSource[] | null;
};

export type Conversation = {
  id: string;
  created_at: string;
  updated_at: string;
  first_question: string | null;
};

export type ChatResponse = {
  answer: string;
  tool?: string | null;
  table?: string | null;
  result?: Record<string, unknown>;
  plan?: Record<string, unknown> | null;
  conversation_id?: string;
  llm?: string;
  llm_used?: boolean;
  sources?: WebSource[] | null;
};

export type HistoryResponse = {
  conversation_id: string;
  messages: ChatMessage[];
};

export type ConversationsResponse = {
  conversations: Conversation[];
};
