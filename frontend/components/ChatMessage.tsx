'use client';

import { ChatMessage as ChatMessageType } from '@/types/chat';

export function ChatMessage({ message }: { message: ChatMessageType }) {
  const isUser = message.role === 'user';
  const meta = [message.tool, message.table].filter(Boolean).join(' • ');
  const sources = message.sources ?? [];

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`flex gap-4 px-4 py-6 ${
          isUser ? 'flex-row-reverse' : 'flex-row'
        }`}
      >
        {/* Avatar */}
        <div
          className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
            isUser
              ? 'bg-[#5436da] text-white'
              : 'bg-[#19c37d] text-white'
          }`}
        >
          {isUser ? 'U' : 'AI'}
        </div>

        {/* Message content */}
        <div className={`max-w-[700px] ${isUser ? 'text-right' : 'text-left'}`}>
          {/* Sender name */}
          <div className={`mb-1 text-sm font-semibold ${isUser ? 'text-[#ececec]' : 'text-[#ececec]'}`}>
            {isUser ? 'You' : 'ChatGPT'}
          </div>

          {/* Message text */}
          <div className="whitespace-pre-wrap text-[15px] leading-[1.6] text-[#d1d5db]">
            {message.content}
          </div>

          {/* Metadata (tool info) */}
          {!isUser && meta && (
            <div className="mt-2 inline-block rounded-md bg-[#2f2f2f] px-2 py-1 text-xs text-[#b4b4b4]">
              {meta}
            </div>
          )}

          {/* Web Sources */}
          {!isUser && sources.length > 0 && (
            <div className="mt-3 rounded-lg border border-[#303030] bg-[#2f2f2f] p-3">
              <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-[#b4b4b4]">
                Sources
              </div>
              <div className="flex flex-col gap-1">
                {sources.map((src, idx) => (
                  <a
                    key={idx}
                    href={src.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-sm text-[#10a37f] hover:underline"
                  >
                    <svg
                      width="12"
                      height="12"
                      viewBox="0 0 12 12"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path
                        d="M4.5 3L4.5 1.5H1.5V10.5H10.5V7.5H9"
                        stroke="currentColor"
                        strokeWidth="1.2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                      <path
                        d="M7 1.5H10.5V5"
                        stroke="currentColor"
                        strokeWidth="1.2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                      <path
                        d="M5.25 6.75L10.5 1.5"
                        stroke="currentColor"
                        strokeWidth="1.2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                    <span className="truncate">{src.title || src.source}</span>
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* Timestamp */}
          {message.timestamp && (
            <div className="mt-2 text-xs text-[#666666]">{message.timestamp}</div>
          )}
        </div>
      </div>
    </div>
  );
}
