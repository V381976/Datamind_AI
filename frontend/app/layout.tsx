import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Trading & Database AI',
  description: 'Trading knowledge chatbot with 7700+ Q&A pairs and PostgreSQL database queries',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
