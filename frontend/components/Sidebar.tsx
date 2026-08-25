'use client';

import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useChat } from '@/contexts/ChatContext';

export function Sidebar() {
  const {
    conversations,
    currentConversationId,
    selectConversation,
    createNewChat,
    deleteConversation,
    renameConversation,
    sidebarOpen,
    setSidebarOpen,
    theme,
    toggleTheme,
  } = useChat();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingId && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editingId]);

  const startRenaming = (id: string, currentTitle: string) => {
    setEditingId(id);
    setEditValue(currentTitle);
  };

  const confirmRename = () => {
    if (editingId && editValue.trim()) {
      renameConversation(editingId, editValue.trim());
    }
    setEditingId(null);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) return 'Today';
    if (days === 1) return 'Yesterday';
    if (days < 7) return `${days} days ago`;
    return date.toLocaleDateString();
  };

  return (
    <>
      {/* Mobile overlay */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm md:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <motion.aside
        initial={false}
        animate={{
          x: sidebarOpen ? 0 : -280,
        }}
        transition={{ type: 'spring', damping: 25, stiffness: 200 }}
        className="glass fixed left-0 top-0 z-40 flex h-full w-[280px] flex-col border-r border-white/5"
      >
        {/* Logo & New Chat */}
        <div className="border-b border-white/5 p-4">
          {/* Logo */}
          <div className="mb-4 flex items-center gap-3">
            <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <path
                  d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"
                  stroke="white"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              <div className="absolute -right-1 -top-1 h-3 w-3 rounded-full bg-green-400 border-2 border-[#0f172a]" />
            </div>
            <div>
              <h1 className="text-lg font-bold gradient-text">DataMind</h1>
              <p className="text-xs text-slate-500">AI Assistant</p>
            </div>
          </div>

          {/* New Chat Button */}
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            type="button"
            onClick={createNewChat}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-indigo-500/30 bg-gradient-to-r from-indigo-500/10 to-purple-500/10 px-4 py-3 text-sm font-medium text-indigo-400 transition-all hover:from-indigo-500/20 hover:to-purple-500/20 hover:border-indigo-500/50"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
            New Conversation
          </motion.button>
        </div>

        {/* Search Bar */}
        <div className="px-4 pt-4">
          <div className="relative">
            <svg
              className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
            >
              <circle cx="11" cy="11" r="8" stroke="currentColor" strokeWidth="2" />
              <path d="M21 21l-4.35-4.35" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
            <input
              type="text"
              placeholder="Search conversations..."
              className="w-full rounded-lg border border-white/5 bg-white/5 py-2 pl-10 pr-4 text-sm text-slate-300 placeholder-slate-500 focus:border-indigo-500/50 focus:outline-none focus:ring-1 focus:ring-indigo-500/30"
            />
          </div>
        </div>

        {/* Conversations List */}
        <div className="flex-1 overflow-y-auto px-3 py-4">
          {conversations.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-white/5">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="text-slate-500">
                  <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <p className="text-sm text-slate-500">No conversations yet</p>
              <p className="text-xs text-slate-600 mt-1">Start a new chat to begin</p>
            </div>
          ) : (
            <div className="space-y-1">
              {conversations.map((conversation, index) => {
                const isActive = conversation.id === currentConversationId;
                const isEditing = editingId === conversation.id;

                return (
                  <motion.div
                    key={conversation.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className={`group relative rounded-xl transition-all duration-200 ${
                      isActive
                        ? 'sidebar-active bg-indigo-500/10'
                        : 'hover:bg-white/5'
                    }`}
                    onMouseEnter={() => setHoveredId(conversation.id)}
                    onMouseLeave={() => setHoveredId(null)}
                  >
                    {isEditing ? (
                      <input
                        ref={inputRef}
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onBlur={confirmRename}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') confirmRename();
                          if (e.key === 'Escape') setEditingId(null);
                        }}
                        className="w-full rounded-lg border border-indigo-500/30 bg-white/5 px-4 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
                      />
                    ) : (
                      <div className="flex items-center gap-3 px-4 py-3">
                        {/* Chat icon */}
                        <div className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg ${
                          isActive
                            ? 'bg-indigo-500/20 text-indigo-400'
                            : 'bg-white/5 text-slate-500 group-hover:text-slate-400'
                        }`}>
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                          </svg>
                        </div>

                        {/* Title & Date */}
                        <div className="flex-1 min-w-0">
                          <button
                            type="button"
                            onClick={() => selectConversation(conversation.id)}
                            className="w-full truncate text-left text-sm font-medium text-slate-300 group-hover:text-white transition-colors"
                          >
                            {conversation.title}
                          </button>
                          <p className="text-xs text-slate-600 mt-0.5">
                            {formatDate(conversation.updated_at)}
                          </p>
                        </div>

                        {/* Action buttons */}
                        <AnimatePresence>
                          {hoveredId === conversation.id && (
                            <motion.div
                              initial={{ opacity: 0, scale: 0.8 }}
                              animate={{ opacity: 1, scale: 1 }}
                              exit={{ opacity: 0, scale: 0.8 }}
                              className="flex items-center gap-1"
                            >
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  startRenaming(conversation.id, conversation.title);
                                }}
                                className="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-white/10 hover:text-white"
                                title="Rename"
                              >
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                                  <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                                  <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                                </svg>
                              </button>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  deleteConversation(conversation.id);
                                }}
                                className="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-red-500/20 hover:text-red-400"
                                title="Delete"
                              >
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                                  <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                                </svg>
                              </button>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    )}
                  </motion.div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-white/5 p-4">
          {/* Theme Toggle */}
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            type="button"
            onClick={toggleTheme}
            className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium text-slate-400 transition-all hover:bg-white/5 hover:text-white"
          >
            {theme === 'dark' ? (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="5" stroke="currentColor" strokeWidth="2" />
                <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
            {theme === 'dark' ? 'Light mode' : 'Dark mode'}
          </motion.button>

          {/* User section */}
          <div className="mt-2 flex items-center gap-3 rounded-xl px-4 py-3 transition-all hover:bg-white/5">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 text-sm font-semibold text-white">
              U
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white">User</p>
              <p className="text-xs text-slate-500">Free Plan</p>
            </div>
            <div className="h-2 w-2 rounded-full bg-green-400" />
          </div>
        </div>
      </motion.aside>
    </>
  );
}
