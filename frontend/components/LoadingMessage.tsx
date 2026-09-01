'use client';

import { useChat } from '@/contexts/ChatContext';

export function LoadingMessage() {
  const { theme } = useChat();

  return (
    <div className="flex justify-start">
      <div className="flex gap-4 px-4 py-6">
        {/* Avatar */}
        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 text-xs font-bold text-white shadow-lg shadow-emerald-500/40">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>

        {/* Loading content */}
        <div>
          <div className="mb-2 text-sm font-semibold text-emerald-400">
            DataMind AI
          </div>
          <div className="glass inline-flex items-center gap-2 rounded-2xl border border-white/10 px-5 py-4 shadow-lg">
            {/* Animated dots */}
            <div className="flex items-center gap-2">
              <div className="h-2.5 w-2.5 rounded-full bg-indigo-400 shadow-lg shadow-indigo-400/50" />
              <div className="h-2.5 w-2.5 rounded-full bg-purple-400 shadow-lg shadow-purple-400/50" />
              <div className="h-2.5 w-2.5 rounded-full bg-pink-400 shadow-lg shadow-pink-400/50" />
            </div>
            <span className="ml-2 text-sm text-slate-400">Thinking...</span>
          </div>
        </div>
      </div>
    </div>
  );
}
