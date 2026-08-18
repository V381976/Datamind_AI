import { Conversation } from '@/types/chat';

interface ChatHistoryProps {
  conversations: Conversation[];
  currentConversationId: string | null;
  onSelectConversation: (conversationId: string) => void;
  onNewChat: () => void;
}

export function ChatHistory({ conversations, currentConversationId, onSelectConversation, onNewChat }: ChatHistoryProps) {
  return (
    <aside className="flex h-full w-72 min-w-[16rem] flex-col border-r border-slate-800 bg-slate-900/80 max-md:absolute max-md:inset-y-0 max-md:left-0 max-md:z-20 max-md:shadow-xl">
      <div className="p-3">
        <button
          type="button"
          onClick={onNewChat}
          className="w-full rounded-lg border border-slate-700 bg-slate-950/70 px-3 py-2 text-sm font-medium text-slate-100 transition hover:border-sky-500/40 hover:bg-slate-900"
        >
          + New chat
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-3">
        {conversations.length === 0 && (
          <div className="px-2 py-4 text-center text-sm text-slate-400">No conversations yet.</div>
        )}
        {conversations.map((conversation) => {
          const isActive = conversation.id === currentConversationId;
          const label = conversation.first_question?.trim() || 'Untitled conversation';
          const shortLabel = label.length > 32 ? `${label.slice(0, 32)}…` : label;
          const updated = new Date(conversation.updated_at).toLocaleString(undefined, {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
          });

          return (
            <button
              key={conversation.id}
              type="button"
              onClick={() => onSelectConversation(conversation.id)}
              className={`mb-1 block w-full rounded-lg px-3 py-2 text-left text-sm transition ${
                isActive
                  ? 'border border-sky-500/40 bg-sky-500/10 text-slate-50'
                  : 'border border-transparent text-slate-200 hover:bg-slate-800/80'
              }`}
            >
              <div className="font-medium leading-snug">{shortLabel}</div>
              <div className="mt-1 text-[11px] text-slate-400">{updated}</div>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
