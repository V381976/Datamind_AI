'use client';

import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { ChatProvider, useChat } from '@/contexts/ChatContext';
import { Sidebar } from '@/components/Sidebar';
import { TopBar } from '@/components/TopBar';
import { MessageBubble } from '@/components/MessageBubble';
import { InputBox } from '@/components/InputBox';
import { LoadingMessage } from '@/components/LoadingMessage';
import { WelcomeScreen } from '@/components/WelcomeScreen';
import { SettingsModal } from '@/components/SettingsModal';

function ChatApp() {
  const {
    messages,
    isLoading,
    theme,
    sidebarOpen,
    settings,
  } = useChat();

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [ThreeBg, setThreeBg] = useState<React.ComponentType | null>(null);

  // Lazy load Three.js background
  useEffect(() => {
    const loadBg = async () => {
      try {
        const mod = await import('@/components/ThreeBackground');
        setThreeBg(() => mod.ThreeBackground);
      } catch {
        // Three.js failed to load, plain background is fine
      }
    };
    const timer = setTimeout(loadBg, 500);
    return () => clearTimeout(timer);
  }, []);

  // Auto-scroll to bottom on new message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const showWelcome = messages.length === 0;

  // Font size classes
  const fontSizeClass = {
    small: 'text-xs',
    medium: 'text-sm',
    large: 'text-base',
  }[settings.fontSize];

  // Compact mode spacing
  const messageSpacing = settings.compactMode ? 'py-2' : 'py-6';

  return (
    <div className={`flex h-screen flex-col bg-[#0a0a1a] text-slate-200 ${
      theme === 'light' ? '!bg-[#f8fafc] !text-[#1e293b]' : ''
    }`}>
      {/* 3D Background */}
      {ThreeBg && <ThreeBg />}

      {/* Settings Modal */}
      <SettingsModal />

      {/* Sidebar */}
      <Sidebar />

      {/* Top Bar */}
      <TopBar />

      {/* Main content area */}
      <div className={`relative z-10 flex flex-1 flex-col pt-16 transition-all duration-300 ${
        sidebarOpen ? 'md:ml-[280px]' : 'ml-0'
      }`}>
        {/* Messages area */}
        <div className={`flex-1 overflow-y-auto ${fontSizeClass}`}>
          {showWelcome ? (
            <WelcomeScreen />
          ) : (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="mx-auto max-w-[768px]"
            >
              {messages.map((message) => (
                <div key={message.id} className={messageSpacing}>
                  <MessageBubble message={message} />
                </div>
              ))}
              {isLoading && <LoadingMessage />}
              <div ref={messagesEndRef} className="h-4" />
            </motion.div>
          )}
        </div>

        {/* Input area */}
        <InputBox />
      </div>
    </div>
  );
}

export default function HomePage() {
  return (
    <ChatProvider>
      <ChatApp />
    </ChatProvider>
  );
}
