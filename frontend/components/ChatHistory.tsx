'use client';

import { Conversation } from '@/types/chat';

interface ChatHistoryProps {
  conversations: Conversation[];
  currentConversationId: string | null;
  onSelectConversation: (conversationId: string) => void;
  onNewChat: () => void;
}

export function ChatHistory({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewChat,
}: ChatHistoryProps) {
  // Group conversations by date
  const groupedConversations = groupByDate(conversations);

  return (
    <aside className="flex h-full w-[260px] flex-col bg-[#171717]">
      {/* New Chat Button */}
      <div className="flex items-center justify-between p-2">
        <button
          type="button"
          onClick={onNewChat}
          className="flex flex-1 items-center gap-2 rounded-lg border border-[#303030] px-3 py-2 text-sm text-[#ececec] transition hover:bg-[#212121]"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M8 3v10M3 8h10"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
          New chat
        </button>
      </div>

      {/* Conversations List */}
      <div className="flex-1 overflow-y-auto px-2 pb-4">
        {Object.entries(groupedConversations).map(([dateLabel, items]) => (
          <div key={dateLabel} className="mb-2">
            <div className="px-3 py-2 text-xs font-semibold text-[#b4b4b4]">{dateLabel}</div>
            {items.map((conversation) => {
              const isActive = conversation.id === currentConversationId;
              const label = conversation.first_question?.trim() || 'New chat';
              const shortLabel = label.length > 28 ? `${label.slice(0, 28)}…` : label;

              return (
                <button
                  key={conversation.id}
                  type="button"
                  onClick={() => onSelectConversation(conversation.id)}
                  className={`mb-0.5 flex w-full items-center rounded-lg px-3 py-2 text-left text-sm transition ${
                    isActive
                      ? 'bg-[#212121] text-[#ececec]'
                      : 'text-[#b4b4b4] hover:bg-[#212121]'
                  }`}
                >
                  <span className="truncate">{shortLabel}</span>
                </button>
              );
            })}
          </div>
        ))}

        {conversations.length === 0 && (
          <div className="px-4 py-8 text-center text-sm text-[#666666]">No conversations yet.</div>
        )}
      </div>

      {/* User section at bottom */}
      <div className="border-t border-[#303030] p-3">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#5436da] text-xs font-semibold text-white">
            U
          </div>
          <span className="text-sm text-[#ececec]">User</span>
        </div>
      </div>
    </aside>
  );
}

function groupByDate(conversations: Conversation[]): Record<string, Conversation[]> {
  const groups: Record<string, Conversation[]> = {};
  const now = new Date();
  const today = now.toDateString();
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);

  conversations.forEach((conv) => {
    const convDate = new Date(conv.updated_at);
    let label: string;

    if (convDate.toDateString() === today) {
      label = 'Today';
    } else if (convDate.toDateString() === yesterday.toDateString()) {
      label = 'Yesterday';
    } else if (now.getTime() - convDate.getTime() < 7 * 24 * 60 * 60 * 1000) {
      label = 'Previous 7 days';
    } else if (now.getTime() - convDate.getTime() < 30 * 24 * 60 * 60 * 1000) {
      label = 'Previous 30 days';
    } else {
      label = 'Older';
    }

    if (!groups[label]) {
      groups[label] = [];
    }
    groups[label].push(conv);
  });

  return groups;
}
