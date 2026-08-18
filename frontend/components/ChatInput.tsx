type ChatInputProps = {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  disabled?: boolean;
};

export function ChatInput({ value, onChange, onSend, disabled = false }: ChatInputProps) {
  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      if (!disabled && value.trim()) {
        onSend();
      }
    }
  };

  return (
    <div className="border-t border-slate-800 bg-slate-950/90 p-3 backdrop-blur-sm">
      <div className="flex items-end gap-3 rounded-2xl border border-slate-700 bg-slate-900/80 p-2 shadow-glow">
        <textarea
          aria-label="Ask about trading or your database"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          disabled={disabled}
          placeholder="Ask about trading, stocks, forex, crypto, or your database..."
          className="max-h-32 min-h-[44px] flex-1 resize-none bg-transparent px-3 py-2 text-sm text-slate-100 placeholder:text-slate-400 focus:outline-none disabled:cursor-not-allowed"
        />
        <button
          type="button"
          onClick={onSend}
          disabled={disabled || !value.trim()}
          className="rounded-xl bg-sky-500 px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-sky-400 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
        >
          {disabled ? 'Sending...' : 'Send'}
        </button>
      </div>
    </div>
  );
}
