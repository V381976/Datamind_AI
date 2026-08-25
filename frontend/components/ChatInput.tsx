'use client';

import { useEffect, useRef } from 'react';

type ChatInputProps = {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  disabled?: boolean;
};

export function ChatInput({ value, onChange, onSend, disabled = false }: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      if (!disabled && value.trim()) {
        onSend();
      }
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [value]);

  return (
    <div className="flex justify-center px-4 pb-6 pt-2">
      <div className="flex w-full max-w-[768px] items-end rounded-2xl bg-[#303030] p-2 shadow-lg">
        <textarea
          ref={textareaRef}
          aria-label="Message input"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          disabled={disabled}
          placeholder="Message ChatGPT..."
          className="max-h-[200px] min-h-[44px] flex-1 resize-none bg-transparent px-3 py-2 text-[15px] text-[#ececec] placeholder:text-[#666666] focus:outline-none disabled:cursor-not-allowed"
        />
        <button
          type="button"
          onClick={onSend}
          disabled={disabled || !value.trim()}
          className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full transition disabled:cursor-not-allowed disabled:opacity-30"
          style={{
            backgroundColor: value.trim() ? '#10a37f' : '#666666',
          }}
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M7 11L12 6L17 11M12 18V7"
              stroke="white"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}
