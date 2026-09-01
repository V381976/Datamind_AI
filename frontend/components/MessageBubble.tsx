'use client';

import { Message } from '@/contexts/ChatContext';
import { useChat } from '@/contexts/ChatContext';
import { MarkdownRenderer } from '@/components/MarkdownRenderer';

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const { theme, settings } = useChat();
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`flex gap-4 px-4 py-4 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
        {/* Avatar */}
        <div className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl text-xs font-bold ${
          isUser
            ? 'bg-gradient-to-br from-indigo-500 to-purple-600 text-white shadow-lg shadow-indigo-500/30'
            : theme === 'light'
              ? 'bg-gradient-to-br from-emerald-500 to-teal-600 text-white shadow-lg shadow-emerald-500/30'
              : 'bg-gradient-to-br from-emerald-500 to-teal-600 text-white shadow-lg shadow-emerald-500/40'
        }`}>
          {isUser ? (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              <circle cx="12" cy="7" r="4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
        </div>

        {/* Message content */}
        <div className={`max-w-[700px] min-w-0 ${isUser ? 'text-right' : 'text-left'}`}>
          {/* Sender name */}
          <div className={`mb-2 text-sm font-semibold ${
            isUser
              ? 'text-indigo-400'
              : 'text-emerald-400'
          }`}>
            {isUser ? 'You' : 'DataMind AI'}
          </div>

          {/* Message bubble */}
          <div className={`rounded-2xl px-5 py-4 transition-all duration-150 ${
            isUser
              ? theme === 'light'
                ? 'bg-gradient-to-br from-indigo-100 to-purple-100 border border-indigo-200 shadow-md hover:shadow-lg'
                : 'bg-gradient-to-br from-indigo-500/25 to-purple-500/25 border border-indigo-500/30 shadow-lg hover:shadow-xl hover:border-indigo-500/40'
              : theme === 'light'
                ? 'bg-gradient-to-br from-white to-slate-50 border border-slate-200 shadow-md hover:shadow-lg'
                : 'glass border border-white/10 shadow-xl hover:shadow-2xl hover:border-white/15'
          }`}>
            <div className={`whitespace-pre-wrap leading-[1.7] ${
              isUser
                ? theme === 'light' ? 'text-slate-800' : 'text-slate-200'
                : ''
            }`}>
              {isUser ? (
                <span>{message.content}</span>
              ) : (
                <MarkdownRenderer content={message.content} />
              )}
            </div>
          </div>

          {/* Sources */}
          {!isUser && message.sources && message.sources.length > 0 && (
            <div className={`mt-3 overflow-hidden rounded-xl border transition-all duration-150 ${
              theme === 'light'
                ? 'border-slate-200 bg-slate-50 shadow-md hover:shadow-lg'
                : 'border-white/5 bg-white/5 shadow-lg hover:shadow-xl'
            }`}>
              <div className={`border-b px-4 py-2 ${
                theme === 'light' ? 'border-slate-200' : 'border-white/5'
              }`}>
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" />
                    <path d="M12 16v-4M12 8h.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                  Sources
                </div>
              </div>
              <div className="p-3">
                {message.sources.map((src, idx) => (
                  <a
                    key={idx}
                    href={src.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-indigo-400 transition-colors hover:bg-indigo-500/10"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="flex-shrink-0">
                      <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      <polyline points="15 3 21 3 21 9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      <line x1="10" y1="14" x2="21" y2="3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    <span className="truncate group-hover:underline">{src.title || src.source}</span>
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* Timestamp */}
          {settings.showTimestamps && message.timestamp && (
            <div className={`mt-2 text-xs ${
              theme === 'light' ? 'text-slate-400' : 'text-slate-600'
            }`}>
              {message.timestamp}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
