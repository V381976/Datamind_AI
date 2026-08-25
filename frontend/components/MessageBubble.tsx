'use client';

import { motion } from 'framer-motion';
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
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      <div className={`flex gap-4 px-4 py-4 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
        {/* Avatar */}
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.1, type: 'spring', damping: 15 }}
          className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl text-xs font-bold ${
            isUser
              ? 'bg-gradient-to-br from-indigo-500 to-purple-600 text-white'
              : theme === 'light'
                ? 'bg-gradient-to-br from-emerald-500 to-teal-600 text-white shadow-lg shadow-emerald-500/20'
                : 'bg-gradient-to-br from-emerald-500 to-teal-600 text-white shadow-lg shadow-emerald-500/30 pulse-ring'
          }`}
        >
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
        </motion.div>

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
          <div
            className={`rounded-2xl px-5 py-4 ${
              isUser
                ? theme === 'light'
                  ? 'bg-indigo-100 border border-indigo-200'
                  : 'bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/20'
                : theme === 'light'
                  ? 'bg-white border border-slate-200 shadow-sm'
                  : 'glass border border-white/5'
            }`}
          >
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
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className={`mt-3 overflow-hidden rounded-xl border ${
                theme === 'light'
                  ? 'border-slate-200 bg-slate-50'
                  : 'border-white/5 bg-white/5'
              }`}
            >
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
            </motion.div>
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
    </motion.div>
  );
}
