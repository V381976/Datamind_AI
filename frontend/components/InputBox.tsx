'use client';

import { useEffect, useRef, useState } from 'react';
import { useChat } from '@/contexts/ChatContext';

export function InputBox() {
  const { sendMessage, isLoading, stopGeneration, settings, theme } = useChat();
  const [input, setInput] = useState('');

  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [input]);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      if (!isLoading && input.trim()) {
        sendMessage(input);
        setInput('');
      }
    }
  };

  const handleSend = () => {
    if (input.trim() && !isLoading) {
      sendMessage(input);
      setInput('');
    }
  };

  const handleStop = () => {
    stopGeneration();
  };

  const tokenCount = input.length;

  return (
    <div className="flex justify-center px-4 pb-6 pt-2">
      <div className="relative w-full max-w-[600px]">
        {/* Input container */}
        <div className="glass relative flex items-end rounded-2xl border border-white/10 p-2 shadow-2xl glow-indigo hover:scale-[1.01] transition-transform duration-150">
          {/* Attachment button */}
          <button
            type="button"
            className="mb-1 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl text-slate-500 transition-colors duration-150 hover:bg-white/5 hover:text-white hover:scale-110"
            title="Attach file (coming soon)"
            disabled
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>

          {/* Textarea */}
          <textarea
            ref={textareaRef}
            aria-label="Message input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={isLoading}
            placeholder="Ask DataMind anything..."
            className="max-h-[200px] min-h-[44px] flex-1 resize-none bg-transparent px-3 py-2.5 text-[15px] text-white placeholder-slate-500 focus:outline-none disabled:cursor-not-allowed"
          />

          {/* Token counter */}
          {tokenCount > 0 && (
            <div className="mb-2 mr-2 text-xs font-mono text-slate-600">
              {tokenCount}
            </div>
          )}

          {/* Send / Stop button */}
          {isLoading ? (
            <button
              type="button"
              onClick={handleStop}
              className="mb-1 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-red-500 to-pink-600 text-white shadow-lg shadow-red-500/30 transition-all duration-150 hover:shadow-red-500/50 hover:scale-110"
              title="Stop generating"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <rect x="6" y="6" width="12" height="12" rx="2" fill="white" />
              </svg>
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSend}
              disabled={!input.trim()}
              className={`mb-1 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl transition-all duration-150 disabled:cursor-not-allowed disabled:opacity-30 ${
                input.trim()
                  ? 'bg-gradient-to-br from-indigo-500 to-purple-600 text-white shadow-lg shadow-indigo-500/30 hover:shadow-indigo-500/50 hover:scale-110'
                  : 'bg-white/10 text-slate-500'
              }`}
              title="Send message"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <path
                  d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          )}
        </div>

        {/* Bottom hints */}
        <div className="mt-3 flex items-center justify-center gap-4 text-xs text-slate-600">
          <span className="flex items-center gap-1">
            <kbd className="rounded border border-white/10 bg-white/5 px-1.5 py-0.5 font-mono text-[10px]">Enter</kbd>
            to send
          </span>
          <span className="flex items-center gap-1">
            <kbd className="rounded border border-white/10 bg-white/5 px-1.5 py-0.5 font-mono text-[10px]">Shift+Enter</kbd>
            for new line
          </span>
        </div>
      </div>
    </div>
  );
}