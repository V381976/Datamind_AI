'use client';

import { useEffect, useState } from 'react';
import { fetchModelStatus, ModelStatus } from '@/lib/api';

interface HeaderProps {
  onToggleSidebar: () => void;
  sidebarOpen: boolean;
}

export function Header({ onToggleSidebar, sidebarOpen }: HeaderProps) {
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
    <header className="fixed left-0 right-0 top-0 z-30 flex h-14 items-center border-b border-[#303030] bg-[#212121] px-4">
      {/* Sidebar toggle button */}
      <button
        type="button"
        onClick={onToggleSidebar}
        className="mr-3 flex h-9 w-9 items-center justify-center rounded-md transition hover:bg-[#303030]"
        aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
      >
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="text-[#b4b4b4]"
        >
          {sidebarOpen ? (
            <path
              fillRule="evenodd"
              clipRule="evenodd"
              d="M8.857 3h6.286c1.084 0 1.958.895 1.958 2v14c0 1.105-.874 2-1.958 2H8.857C7.773 21 6.9 20.105 6.9 19V5c0-1.105.873-2 1.957-2zm0 2v14h6.286V5H8.857zM4 6h2v12H4V6zm14 0h2v12h-2V6z"
              fill="currentColor"
            />
          ) : (
            <path
              fillRule="evenodd"
              clipRule="evenodd"
              d="M8.857 3h6.286c1.084 0 1.958.895 1.958 2v14c0 1.105-.874 2-1.958 2H8.857C7.773 21 6.9 20.105 6.9 19V5c0-1.105.873-2 1.957-2zm0 2v14h6.286V5H8.857zM3 6h2v12H3V6zm16 0h2v12h-2V6z"
              fill="currentColor"
            />
          )}
        </svg>
      </button>

      {/* Model selector / Title */}
      <div className="flex items-center gap-2">
        <span className="text-base font-semibold text-[#ececec]">ChatGPT</span>
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="text-[#b4b4b4]"
        >
          <path d="M4.5 6L8 9.5L11.5 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>

      {/* Status indicators */}
      <div className="ml-auto flex items-center gap-2">
        <StatusIndicator connected={Boolean(connected)} llmReady={Boolean(llmReady)} />
      </div>
    </header>
  );
}

function StatusIndicator({ connected, llmReady }: { connected: boolean; llmReady: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <div
        className={`h-2 w-2 rounded-full ${connected ? 'bg-[#10a37f]' : 'bg-[#ef4444]'}`}
        title={connected ? 'Database connected' : 'Database disconnected'}
      />
      <div
        className={`h-2 w-2 rounded-full ${llmReady ? 'bg-[#10a37f]' : 'bg-[#f59e0b]'}`}
        title={llmReady ? 'LLM ready' : 'LLM loading'}
      />
    </div>
  );
}
