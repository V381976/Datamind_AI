'use client';

import { useEffect, useState } from 'react';
import { fetchModelStatus, ModelStatus } from '@/lib/api';

export function Header() {
  const [status, setStatus] = useState<ModelStatus | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const loadStatus = async () => {
      try {
        const data = await fetchModelStatus();
        if (!cancelled) {
          setStatus(data);
          setError(false);
        }
      } catch {
        if (!cancelled) {
          setError(true);
        }
      }
    };

    void loadStatus();
    const interval = window.setInterval(loadStatus, 30000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  const connected = !error && status?.database?.connected;
  const llmReady = !error && status?.custom_llm_ready;

  return (
    <header className="border-b border-slate-800 bg-slate-950/80 px-4 py-4 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-50">Trading & Database AI</h1>
          <p className="mt-1 text-xs text-slate-400">7700+ trading answers • Custom LLM • PostgreSQL</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge
            label={connected ? 'Database connected' : error ? 'Backend offline' : 'Database offline'}
            ok={Boolean(connected)}
          />
          <StatusBadge label={llmReady ? 'LLM ready' : 'LLM loading'} ok={Boolean(llmReady)} />
        </div>
      </div>
    </header>
  );
}

function StatusBadge({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${
        ok
          ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
          : 'border-amber-500/30 bg-amber-500/10 text-amber-300'
      }`}
    >
      <span className={`h-2 w-2 rounded-full ${ok ? 'bg-emerald-400' : 'bg-amber-400'}`} />
      {label}
    </div>
  );
}
