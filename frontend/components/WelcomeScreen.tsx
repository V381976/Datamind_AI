'use client';

import { useChat } from '@/contexts/ChatContext';

export function WelcomeScreen() {
  const { sendMessage, theme } = useChat();

  const suggestions = [
    {
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ),
      title: 'Explain a concept',
      prompt: 'Explain quantum computing in simple terms',
      gradient: 'from-blue-500/20 to-cyan-500/20',
      border: 'border-blue-500/20 hover:border-blue-500/40',
      iconColor: 'text-blue-400',
    },
    {
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" stroke="currentColor" strokeWidth="2" />
          <path d="M8 12h8M12 8v8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      ),
      title: 'Help me write code',
      prompt: 'Write a Python function to sort a list of dictionaries by a key',
      gradient: 'from-green-500/20 to-emerald-500/20',
      border: 'border-green-500/20 hover:border-green-500/40',
      iconColor: 'text-green-400',
    },
    {
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
          <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ),
      title: 'Analyze text',
      prompt: 'Analyze the sentiment of this review and provide key themes',
      gradient: 'from-purple-500/20 to-pink-500/20',
      border: 'border-purple-500/20 hover:border-purple-500/40',
      iconColor: 'text-purple-400',
    },
    {
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
          <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ),
      title: 'Brainstorm ideas',
      prompt: 'Give me 5 creative project ideas for a portfolio',
      gradient: 'from-amber-500/20 to-orange-500/20',
      border: 'border-amber-500/20 hover:border-amber-500/40',
      iconColor: 'text-amber-400',
    },
  ];

  return (
    <div className="flex h-full flex-col items-center justify-center px-4">
      {/* Logo */}
      <div className="mb-8 relative">
        <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 shadow-2xl shadow-indigo-500/40 glow-purple">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none">
            <path
              d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"
              stroke="white"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      </div>

      {/* Greeting */}
      <div className="text-center">
        <h2 className="mb-3 text-3xl font-bold gradient-text">
          How can I help you today?
        </h2>
        <p className="mb-10 text-slate-500">
          Ask me anything about technology, AI, programming, or general knowledge.
        </p>
      </div>

      {/* Suggestion cards */}
      <div className="grid w-full max-w-2xl grid-cols-1 gap-4 sm:grid-cols-2">
        {suggestions.map((suggestion, index) => (
          <button
            key={suggestion.title}
            type="button"
            onClick={() => sendMessage(suggestion.prompt)}
            className={`welcome-card group flex items-start gap-4 rounded-2xl border bg-gradient-to-br p-5 text-left transition-all shadow-lg hover:shadow-xl ${suggestion.gradient} ${suggestion.border}`}
          >
            <div className={`flex-shrink-0 rounded-xl bg-white/5 p-2 ${suggestion.iconColor} transition-transform duration-150 group-hover:scale-110`}>
              {suggestion.icon}
            </div>
            <div className="min-w-0">
              <div className="mb-1 text-sm font-semibold text-white">
                {suggestion.title}
              </div>
              <div className="text-xs text-slate-400 line-clamp-2">
                {suggestion.prompt}
              </div>
            </div>
          </button>
        ))}
      </div>

      {/* Bottom hint */}
      <p className="mt-8 text-xs text-slate-600">
        Powered by DataMind AI • Custom LLM
      </p>
    </div>
  );
}
