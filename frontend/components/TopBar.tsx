'use client';

import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useChat } from '@/contexts/ChatContext';

export function TopBar() {
  const {
    chatTitle,
    setChatTitle,
    renameConversation,
    currentConversationId,
    settings,
    updateSettings,
    setShowSettings,
    sidebarOpen,
    setSidebarOpen,
    theme,
  } = useChat();

  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(chatTitle);
  const [showModelDropdown, setShowModelDropdown] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowModelDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const startEditing = () => {
    setEditValue(chatTitle);
    setIsEditing(true);
  };

  const confirmEdit = () => {
    if (editValue.trim()) {
      setChatTitle(editValue.trim());
      if (currentConversationId) {
        renameConversation(currentConversationId, editValue.trim());
      }
    }
    setIsEditing(false);
  };

  const models = ['MyModel-v1', 'MyModel-v2-fast', 'MyModel-v2-accurate'];

  return (
    <header className="glass fixed left-0 right-0 top-0 z-30 flex h-16 items-center justify-between border-b border-white/5 px-4">
      {/* Left side */}
      <div className="flex items-center gap-4">
        {/* Sidebar toggle */}
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          type="button"
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="flex h-10 w-10 items-center justify-center rounded-xl text-slate-400 transition-colors hover:bg-white/5 hover:text-white"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path
              d="M4 6h16M4 12h16M4 18h16"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </motion.button>

        {/* Editable title */}
        {isEditing ? (
          <input
            ref={inputRef}
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onBlur={confirmEdit}
            onKeyDown={(e) => {
              if (e.key === 'Enter') confirmEdit();
              if (e.key === 'Escape') setIsEditing(false);
            }}
            className="rounded-lg border border-indigo-500/30 bg-white/5 px-3 py-1.5 text-base font-semibold text-white focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
          />
        ) : (
          <motion.button
            type="button"
            onClick={startEditing}
            className="group flex items-center gap-2 text-base font-semibold text-slate-300 transition-colors hover:text-white"
          >
            <span className="max-w-[200px] truncate md:max-w-none">{chatTitle}</span>
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              className="text-slate-600 opacity-0 transition-opacity group-hover:opacity-100"
            >
              <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </motion.button>
        )}
      </div>

      {/* Right side */}
      <div className="flex items-center gap-3">
        {/* Model selector */}
        <div className="relative" ref={dropdownRef}>
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            type="button"
            onClick={() => setShowModelDropdown(!showModelDropdown)}
            className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 transition-all hover:border-indigo-500/30 hover:bg-indigo-500/10"
          >
            <div className="h-2 w-2 rounded-full bg-green-400" />
            <span>{settings.model}</span>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" className="text-slate-500">
              <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </motion.button>

          <AnimatePresence>
            {showModelDropdown && (
              <motion.div
                initial={{ opacity: 0, y: -10, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -10, scale: 0.95 }}
                transition={{ duration: 0.15 }}
                className="glass absolute right-0 top-full mt-2 w-56 overflow-hidden rounded-xl border border-white/10 shadow-xl"
              >
                <div className="p-2">
                  {models.map((model) => (
                    <button
                      key={model}
                      type="button"
                      onClick={() => {
                        updateSettings({ model });
                        setShowModelDropdown(false);
                      }}
                      className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all ${
                        settings.model === model
                          ? 'bg-indigo-500/20 text-indigo-400'
                          : 'text-slate-300 hover:bg-white/5 hover:text-white'
                      }`}
                    >
                      <div className={`h-2 w-2 rounded-full ${
                        settings.model === model ? 'bg-indigo-400' : 'bg-slate-600'
                      }`} />
                      {model}
                      {settings.model === model && (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="ml-auto text-indigo-400">
                          <path d="M20 6L9 17l-5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      )}
                    </button>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Settings button */}
        <motion.button
          whileHover={{ scale: 1.05, rotate: 30 }}
          whileTap={{ scale: 0.95 }}
          type="button"
          onClick={() => setShowSettings(true)}
          className="flex h-10 w-10 items-center justify-center rounded-xl text-slate-400 transition-colors hover:bg-white/5 hover:text-white"
          title="Settings"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="2" />
            <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </motion.button>
      </div>
    </header>
  );
}
