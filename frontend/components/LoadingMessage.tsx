export function LoadingMessage() {
  return (
    <div className="flex justify-start">
      <div className="rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 shadow-md">
        <div className="mb-1 text-[11px] font-medium uppercase tracking-[0.16em] text-slate-400">AI</div>
        <div className="flex items-center gap-2 text-sm text-slate-200">
          <span className="inline-flex gap-1">
            <span className="h-2 w-2 animate-bounce rounded-full bg-sky-400 [animation-delay:-0.2s]" />
            <span className="h-2 w-2 animate-bounce rounded-full bg-sky-400 [animation-delay:-0.1s]" />
            <span className="h-2 w-2 animate-bounce rounded-full bg-sky-400" />
          </span>
          <span>Thinking...</span>
        </div>
      </div>
    </div>
  );
}
