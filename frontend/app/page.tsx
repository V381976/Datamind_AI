'use client';

import { useEffect, useRef, useState } from 'react';
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
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);

  // Auto-scroll to bottom on new message
  useEffect(() => {
    const scrollToBottom = () => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };
    
    // Delay scroll slightly to ensure content is rendered
    const timeoutId = setTimeout(scrollToBottom, 100);
    return () => clearTimeout(timeoutId);
  }, [messages, isLoading]);

  // Handle scroll to show/hide scroll button
  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
      setShowScrollButton(!isNearBottom);
    };

    container.addEventListener('scroll', handleScroll);
    return () => container.removeEventListener('scroll', handleScroll);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

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
      {/* Settings Modal */}
      <SettingsModal />

      {/* Sidebar */}
      <Sidebar />

      {/* Top Bar */}
      <TopBar />

      {/* Main content area */}
      <div className={`relative z-10 flex h-[calc(100vh-64px)] flex-col pt-16 transition-all duration-300 ${
        sidebarOpen ? 'md:ml-[280px]' : 'ml-0'
      }`}>
        {/* Messages area */}
        <div 
          ref={messagesContainerRef}
          className={`flex-1 overflow-y-auto ${fontSizeClass} scroll-smooth`}
        >
          {showWelcome ? (
            <WelcomeScreen />
          ) : (
            <div className="mx-auto max-w-[768px] px-4">
              {messages.map((message) => (
                <div key={message.id} className={messageSpacing}>
                  <MessageBubble message={message} />
                </div>
              ))}
              {isLoading && <LoadingMessage />}
              <div ref={messagesEndRef} className="h-4" />
            </div>
          )}
        </div>

        {/* Scroll to bottom button */}
        {showScrollButton && (
          <button
            onClick={scrollToBottom}
            className="absolute bottom-32 right-4 md:right-8 z-20 flex h-10 w-10 items-center justify-center rounded-full bg-indigo-500/90 text-white shadow-lg shadow-indigo-500/30 backdrop-blur-sm transition-all duration-150 hover:bg-indigo-500 hover:scale-110"
            title="Scroll to bottom"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M12 5v14M5 12l7 7 7-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        )}

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
