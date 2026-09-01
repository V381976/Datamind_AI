import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'DataMind AI — Intelligent Assistant',
  description: 'A premium AI chatbot interface powered by custom LLM with trading, coding, and database capabilities',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-[#0a0a1a]">{children}</body>
    </html>
  );
}
