import { ChatMessage as ChatMessageType } from '@/types/chat';

export function ChatMessage({ message }: { message: ChatMessageType }) {
  const isUser = message.role === 'user';
  const meta = [message.tool, message.table].filter(Boolean).join(' • ');

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] rounded-2xl border px-4 py-3 shadow-md ${
          isUser
            ? 'border-sky-500/40 bg-sky-500/10 text-sky-50'
            : 'border-slate-700 bg-slate-900/80 text-slate-100'
        }`}
      >
        <div className="mb-1 text-[11px] font-medium uppercase tracking-[0.16em] text-slate-400">
          {isUser ? 'You' : 'AI'}
        </div>
        <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
        {!isUser && meta && (
          <div className="mt-2 rounded-lg border border-slate-700/80 bg-slate-950/50 px-2 py-1 text-[11px] text-slate-400">
            Source: {meta}
          </div>
        )}
        <div className="mt-2 text-right text-[10px] text-slate-400">{message.timestamp}</div>
      </div>
    </div>
  );
}
