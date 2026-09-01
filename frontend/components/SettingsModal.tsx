'use client';

import { useState, useEffect } from 'react';
import { useChat } from '@/contexts/ChatContext';

export function SettingsModal() {
  const { settings, updateSettings, showSettings, setShowSettings, theme, toggleTheme } = useChat();
  const [localSettings, setLocalSettings] = useState(settings);

  useEffect(() => {
    setLocalSettings(settings);
  }, [settings, showSettings]);

  const handleSave = () => {
    updateSettings(localSettings);
    setShowSettings(false);
  };

  const handleCancel = () => {
    setLocalSettings(settings);
    setShowSettings(false);
  };

  const handleReset = () => {
    setLocalSettings({
      temperature: 0.7,
      maxTokens: 2000,
      systemPrompt: 'You are a helpful AI assistant. You can help with questions about technology, AI, programming, trading, general knowledge, and almost any topic.',
      model: 'MyModel-v1',
      fontSize: 'medium',
      sendOnEnter: true,
      showTimestamps: true,
      compactMode: false,
    });
  };

  return (
    <>
      {showSettings && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            onClick={handleCancel}
          />

          {/* Modal */}
          <div className="glass relative z-10 w-full max-w-lg max-h-[85vh] overflow-y-auto rounded-3xl border border-white/10 p-6 shadow-2xl">
            {/* Header */}
            <div className="mb-6 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="12" r="3" stroke="white" strokeWidth="2" />
                    <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
                <div>
                  <h2 className="text-lg font-bold text-white">Settings</h2>
                  <p className="text-xs text-slate-500">Customize your experience</p>
                </div>
              </div>
              <button
                type="button"
                onClick={handleCancel}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-white/10 hover:text-white hover:scale-110 hover:rotate-90"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                  <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
              </motion.button>
            </div>

            {/* Theme Section */}
            <div className="mb-6">
              <h3 className="mb-3 text-sm font-semibold text-slate-400 uppercase tracking-wider">Appearance</h3>
              <div className="rounded-xl border border-white/5 bg-white/5 p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {theme === 'dark' ? (
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className="text-indigo-400">
                        <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    ) : (
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className="text-amber-400">
                        <circle cx="12" cy="12" r="5" stroke="currentColor" strokeWidth="2" />
                        <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                      </svg>
                    )}
                    <div>
                      <p className="text-sm font-medium text-white">Theme</p>
                      <p className="text-xs text-slate-500">{theme === 'dark' ? 'Dark mode' : 'Light mode'}</p>
                    </div>
                  </div>
                  {/* Toggle switch */}
                  <button
                    type="button"
                    onClick={toggleTheme}
                    className={`relative h-7 w-12 rounded-full transition-colors ${
                      theme === 'dark' ? 'bg-indigo-500' : 'bg-slate-600'
                    }`}
                  >
                    <div
                      className={`absolute top-0.5 h-6 w-6 rounded-full bg-white shadow-md transition-transform ${
                        theme === 'dark' ? 'translate-x-5' : 'translate-x-0.5'
                      }`}
                    />
                  </button>
                </div>
              </div>
            </div>

            {/* Model Section */}
            <div className="mb-6">
              <h3 className="mb-3 text-sm font-semibold text-slate-400 uppercase tracking-wider">Model</h3>
              <div className="space-y-2">
                {['MyModel-v1', 'MyModel-v2-fast', 'MyModel-v2-accurate'].map((model) => (
                  <button
                    key={model}
                    type="button"
                    onClick={() => setLocalSettings({ ...localSettings, model })}
                    className={`flex w-full items-center gap-3 rounded-xl border p-3 text-left transition-all ${
                      localSettings.model === model
                        ? 'border-indigo-500/50 bg-indigo-500/10'
                        : 'border-white/5 bg-white/5 hover:bg-white/10'
                    }`}
                  >
                    <div className={`h-3 w-3 rounded-full ${
                      localSettings.model === model ? 'bg-indigo-400' : 'bg-slate-600'
                    }`} />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-white">{model}</p>
                      <p className="text-xs text-slate-500">
                        {model === 'MyModel-v1' && 'Balanced performance'}
                        {model === 'MyModel-v2-fast' && 'Optimized for speed'}
                        {model === 'MyModel-v2-accurate' && 'Best accuracy'}
                      </p>
                    </div>
                    {localSettings.model === model && (
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" className="text-indigo-400">
                        <path d="M20 6L9 17l-5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* Temperature */}
            <div className="mb-6">
              <div className="mb-3 flex items-center justify-between">
                <label className="text-sm font-medium text-slate-300">Temperature</label>
                <span className="rounded-lg bg-indigo-500/20 px-2.5 py-1 text-xs font-mono font-bold text-indigo-400">
                  {localSettings.temperature}
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={localSettings.temperature}
                onChange={(e) =>
                  setLocalSettings({ ...localSettings, temperature: parseFloat(e.target.value) })
                }
                className="w-full"
              />
              <div className="mt-2 flex justify-between text-xs text-slate-600">
                <span>Precise</span>
                <span>Balanced</span>
                <span>Creative</span>
              </div>
            </div>

            {/* Max Tokens */}
            <div className="mb-6">
              <label className="mb-2 block text-sm font-medium text-slate-300">Max Tokens</label>
              <input
                type="number"
                min="100"
                max="4000"
                step="100"
                value={localSettings.maxTokens}
                onChange={(e) =>
                  setLocalSettings({ ...localSettings, maxTokens: parseInt(e.target.value) || 2000 })
                }
                className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white placeholder-slate-500"
              />
              <p className="mt-2 text-xs text-slate-600">
                Maximum length of the AI response (100-4000)
              </p>
            </div>

            {/* Font Size */}
            <div className="mb-6">
              <h3 className="mb-3 text-sm font-semibold text-slate-400 uppercase tracking-wider">Text Size</h3>
              <div className="flex gap-2">
                {[
                  { value: 'small' as const, label: 'Small', size: 'text-xs' },
                  { value: 'medium' as const, label: 'Medium', size: 'text-sm' },
                  { value: 'large' as const, label: 'Large', size: 'text-base' },
                ].map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setLocalSettings({ ...localSettings, fontSize: option.value })}
                    className={`flex-1 rounded-xl border p-3 text-center transition-all ${
                      localSettings.fontSize === option.value
                        ? 'border-indigo-500/50 bg-indigo-500/10 text-indigo-400'
                        : 'border-white/5 bg-white/5 text-slate-400 hover:bg-white/10'
                    }`}
                  >
                    <span className={option.size}>Aa</span>
                    <p className="mt-1 text-xs">{option.label}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Toggles */}
            <div className="mb-6 space-y-3">
              <h3 className="mb-3 text-sm font-semibold text-slate-400 uppercase tracking-wider">Preferences</h3>
              
              {/* Send on Enter */}
              <div className="flex items-center justify-between rounded-xl border border-white/5 bg-white/5 p-4">
                <div>
                  <p className="text-sm font-medium text-white">Send on Enter</p>
                  <p className="text-xs text-slate-500">Press Enter to send, Shift+Enter for new line</p>
                </div>
                <button
                  type="button"
                  onClick={() => setLocalSettings({ ...localSettings, sendOnEnter: !localSettings.sendOnEnter })}
                  className={`relative h-6 w-11 rounded-full transition-colors ${
                    localSettings.sendOnEnter ? 'bg-indigo-500' : 'bg-slate-600'
                  }`}
                >
                  <div
                    className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
                      localSettings.sendOnEnter ? 'translate-x-5' : 'translate-x-0.5'
                    }`}
                  />
                </button>
              </div>

              {/* Show Timestamps */}
              <div className="flex items-center justify-between rounded-xl border border-white/5 bg-white/5 p-4">
                <div>
                  <p className="text-sm font-medium text-white">Show Timestamps</p>
                  <p className="text-xs text-slate-500">Display time on each message</p>
                </div>
                <button
                  type="button"
                  onClick={() => setLocalSettings({ ...localSettings, showTimestamps: !localSettings.showTimestamps })}
                  className={`relative h-6 w-11 rounded-full transition-colors ${
                    localSettings.showTimestamps ? 'bg-indigo-500' : 'bg-slate-600'
                  }`}
                >
                  <div
                    className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
                      localSettings.showTimestamps ? 'translate-x-5' : 'translate-x-0.5'
                    }`}
                  />
                </button>
              </div>

              {/* Compact Mode */}
              <div className="flex items-center justify-between rounded-xl border border-white/5 bg-white/5 p-4">
                <div>
                  <p className="text-sm font-medium text-white">Compact Mode</p>
                  <p className="text-xs text-slate-500">Reduce spacing between messages</p>
                </div>
                <button
                  type="button"
                  onClick={() => setLocalSettings({ ...localSettings, compactMode: !localSettings.compactMode })}
                  className={`relative h-6 w-11 rounded-full transition-colors ${
                    localSettings.compactMode ? 'bg-indigo-500' : 'bg-slate-600'
                  }`}
                >
                  <div
                    className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
                      localSettings.compactMode ? 'translate-x-5' : 'translate-x-0.5'
                    }`}
                  />
                </button>
              </div>
            </div>

            {/* System Prompt */}
            <div className="mb-6">
              <label className="mb-2 block text-sm font-medium text-slate-300">System Prompt</label>
              <textarea
                value={localSettings.systemPrompt}
                onChange={(e) =>
                  setLocalSettings({ ...localSettings, systemPrompt: e.target.value })
                }
                rows={4}
                className="w-full resize-none rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white placeholder-slate-500"
                placeholder="Instructions for the AI model..."
              />
              <p className="mt-2 text-xs text-slate-600">
                Custom instructions that define the AI's behavior
              </p>
            </div>

            {/* Buttons */}
            <div className="flex items-center justify-between">
              <button
                type="button"
                onClick={handleReset}
                className="rounded-xl px-4 py-2.5 text-sm font-medium text-slate-500 transition-colors hover:text-white"
              >
                Reset to defaults
              </button>
              <div className="flex gap-3">
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  type="button"
                  onClick={handleCancel}
                  className="rounded-xl px-5 py-2.5 text-sm font-medium text-slate-400 transition-colors hover:bg-white/5 hover:text-white"
                >
                  Cancel
                </motion.button>
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  type="button"
                  onClick={handleSave}
                  className="rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 px-5 py-2.5 text-sm font-medium text-white shadow-lg shadow-indigo-500/30 transition-all hover:shadow-indigo-500/50"
                >
                  Save changes
                </motion.button>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
