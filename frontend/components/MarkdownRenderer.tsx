'use client';

import React, { useState, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';

// Custom hook for theme
function useTheme() {
  if (typeof window === 'undefined') return 'dark';
  return document.documentElement.classList.contains('light') ? 'light' : 'dark';
}

// Copy button for code blocks
function CopyButton({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
        copied
          ? 'bg-green-500/20 text-green-400'
          : 'text-slate-500 hover:bg-white/10 hover:text-white'
      }`}
    >
      {copied ? (
        <>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <path d="M20 6L9 17l-5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Copied!
        </>
      ) : (
        <>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" stroke="currentColor" strokeWidth="2" />
            <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" stroke="currentColor" strokeWidth="2" />
          </svg>
          Copy
        </>
      )}
    </button>
  );
}

// Language icon
function LanguageIcon({ language }: { language: string }) {
  const icons: Record<string, string> = {
    javascript: 'JS',
    typescript: 'TS',
    python: 'PY',
    jsx: 'JSX',
    tsx: 'TSX',
    html: 'HTML',
    css: 'CSS',
    json: 'JSON',
    bash: 'SH',
    shell: 'SH',
    sql: 'SQL',
    rust: 'RS',
    go: 'GO',
    java: 'JA',
    cpp: 'C++',
    c: 'C',
    ruby: 'RB',
    php: 'PH',
  };

  return (
    <span className="rounded bg-indigo-500/20 px-1.5 py-0.5 text-[10px] font-bold text-indigo-400">
      {icons[language] || language.toUpperCase()}
    </span>
  );
}

// Custom components for Markdown
function MarkdownComponents({ theme }: { theme: string }) {
  return {
    // Headings
    h1: ({ children, ...props }: any) => (
      <h1
        className={`mt-8 mb-4 text-2xl font-bold ${
          theme === 'light' ? 'text-slate-900' : 'text-white'
        }`}
        {...props}
      >
        {children}
      </h1>
    ),
    h2: ({ children, ...props }: any) => (
      <h2
        className={`mt-6 mb-3 text-xl font-bold ${
          theme === 'light' ? 'text-slate-800' : 'text-white'
        }`}
        {...props}
      >
        {children}
      </h2>
    ),
    h3: ({ children, ...props }: any) => (
      <h3
        className={`mt-5 mb-2 text-lg font-semibold ${
          theme === 'light' ? 'text-slate-800' : 'text-white'
        }`}
        {...props}
      >
        {children}
      </h3>
    ),
    h4: ({ children, ...props }: any) => (
      <h4
        className={`mt-4 mb-2 text-base font-semibold ${
          theme === 'light' ? 'text-slate-700' : 'text-slate-200'
        }`}
        {...props}
      >
        {children}
      </h4>
    ),

    // Paragraphs
    p: ({ children, ...props }: any) => (
      <p
        className={`mb-4 leading-relaxed ${
          theme === 'light' ? 'text-slate-700' : 'text-slate-300'
        }`}
        {...props}
      >
        {children}
      </p>
    ),

    // Bold
    strong: ({ children, ...props }: any) => (
      <strong className={`font-bold ${
        theme === 'light' ? 'text-slate-900' : 'text-white'
      }`} {...props}>
        {children}
      </strong>
    ),

    // Italic
    em: ({ children, ...props }: any) => (
      <em className="italic text-indigo-400" {...props}>
        {children}
      </em>
    ),

    // Inline code
    code: ({ inline, className, children, ...props }: any) => {
      if (inline) {
        return (
          <code
            className={`rounded-md border px-1.5 py-0.5 text-sm font-mono ${
              theme === 'light'
                ? 'border-slate-300 bg-slate-100 text-pink-600'
                : 'border-indigo-500/30 bg-indigo-500/10 text-indigo-300'
            }`}
            {...props}
          >
            {children}
          </code>
        );
      }
      return (
        <code className={className} {...props}>
          {children}
        </code>
      );
    },

    // Code blocks with syntax highlighting
    pre: ({ children, ...props }: any) => {
      const codeElement = children?.props?.children;
      const language = children?.props?.className?.replace('language-', '') || 'text';
      const code = typeof codeElement === 'string' ? codeElement : String(codeElement || '');

      return (
        <div className={`my-4 overflow-hidden rounded-xl border ${
          theme === 'light'
            ? 'border-slate-200 bg-slate-50'
            : 'border-white/10 bg-[#0d1117]'
        }`}>
          {/* Code header */}
          <div className={`flex items-center justify-between border-b px-4 py-2 ${
            theme === 'light'
              ? 'border-slate-200 bg-slate-100'
              : 'border-white/5 bg-[#161b22]'
          }`}>
            <div className="flex items-center gap-2">
              <div className="flex gap-1.5">
                <div className="h-3 w-3 rounded-full bg-red-500/60" />
                <div className="h-3 w-3 rounded-full bg-yellow-500/60" />
                <div className="h-3 w-3 rounded-full bg-green-500/60" />
              </div>
              <LanguageIcon language={language} />
              <span className={`text-xs font-mono ${
                theme === 'light' ? 'text-slate-500' : 'text-slate-500'
              }`}>
                {language}
              </span>
            </div>
            <CopyButton code={code} />
          </div>

          {/* Code content */}
          <pre className={`overflow-x-auto p-4 text-sm font-mono ${
            theme === 'light' ? 'text-slate-800' : 'text-slate-300'
          }`} {...props}>
            {children}
          </pre>
        </div>
      );
    },

    // Lists
    ul: ({ children, ...props }: any) => (
      <ul
        className={`mb-4 ml-6 list-disc space-y-2 ${
          theme === 'light' ? 'text-slate-700' : 'text-slate-300'
        }`}
        {...props}
      >
        {children}
      </ul>
    ),
    ol: ({ children, ...props }: any) => (
      <ol
        className={`mb-4 ml-6 list-decimal space-y-2 ${
          theme === 'light' ? 'text-slate-700' : 'text-slate-300'
        }`}
        {...props}
      >
        {children}
      </ol>
    ),
    li: ({ children, ...props }: any) => (
      <li className="pl-2" {...props}>
        {children}
      </li>
    ),

    // Blockquotes (tips, notes, warnings)
    blockquote: ({ children, ...props }: any) => {
      const text = String(children);
      let type = 'note';
      let icon = '💡';
      let colors = 'border-blue-500/50 bg-blue-500/10';

      if (text.toLowerCase().includes('warning') || text.toLowerCase().includes('caution')) {
        type = 'warning';
        icon = '⚠️';
        colors = 'border-amber-500/50 bg-amber-500/10';
      } else if (text.toLowerCase().includes('tip') || text.toLowerCase().includes('pro tip')) {
        type = 'tip';
        icon = '💡';
        colors = 'border-green-500/50 bg-green-500/10';
      } else if (text.toLowerCase().includes('important') || text.toLowerCase().includes('note')) {
        type = 'note';
        icon = '📝';
        colors = 'border-indigo-500/50 bg-indigo-500/10';
      } else if (text.toLowerCase().includes('example')) {
        type = 'example';
        icon = '📌';
        colors = 'border-purple-500/50 bg-purple-500/10';
      }

      return (
        <div className={`my-4 rounded-xl border-l-4 p-4 ${colors}`}>
          <div className="flex items-start gap-3">
            <span className="text-lg">{icon}</span>
            <div className={`flex-1 text-sm ${
              theme === 'light' ? 'text-slate-700' : 'text-slate-300'
            }`}>
              {children}
            </div>
          </div>
        </div>
      );
    },

    // Tables
    table: ({ children, ...props }: any) => (
      <div className="my-4 overflow-x-auto rounded-xl border border-white/10">
        <table className="w-full text-sm" {...props}>
          {children}
        </table>
      </div>
    ),
    thead: ({ children, ...props }: any) => (
      <thead className={`border-b ${
        theme === 'light'
          ? 'border-slate-200 bg-slate-100'
          : 'border-white/10 bg-white/5'
      }`} {...props}>
        {children}
      </thead>
    ),
    tbody: ({ children, ...props }: any) => (
      <tbody className={theme === 'light' ? 'divide-y divide-slate-200' : 'divide-y divide-white/5'} {...props}>
        {children}
      </tbody>
    ),
    tr: ({ children, ...props }: any) => (
      <tr className={`transition-colors ${
        theme === 'light' ? 'hover:bg-slate-50' : 'hover:bg-white/5'
      }`} {...props}>
        {children}
      </tr>
    ),
    th: ({ children, ...props }: any) => (
      <th className={`px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider ${
        theme === 'light'
          ? 'text-slate-600'
          : 'text-slate-400'
      }`} {...props}>
        {children}
      </th>
    ),
    td: ({ children, ...props }: any) => (
      <td className={`px-4 py-3 ${
        theme === 'light' ? 'text-slate-700' : 'text-slate-300'
      }`} {...props}>
        {children}
      </td>
    ),

    // Horizontal rules
    hr: (props: any) => (
      <hr className={`my-6 border-t ${
        theme === 'light' ? 'border-slate-200' : 'border-white/10'
      }`} {...props} />
    ),

    // Links
    a: ({ children, href, ...props }: any) => (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-indigo-400 underline decoration-indigo-400/30 transition-colors hover:text-indigo-300 hover:decoration-indigo-400/50"
        {...props}
      >
        {children}
      </a>
    ),

    // Images
    img: ({ src, alt, ...props }: any) => (
      <img
        src={src}
        alt={alt}
        className="my-4 max-w-full rounded-xl"
        {...props}
      />
    ),
  };
}

// Main renderer component
export function MarkdownRenderer({ content }: { content: string }) {
  const theme = useTheme();
  const components = useMemo(() => MarkdownComponents({ theme }), [theme]);

  // Pre-process content to enhance formatting
  const enhancedContent = useMemo(() => {
    let text = content;

    // Convert **bold** patterns to ensure they render
    // (react-markdown handles this, but we ensure consistency)

    // Add spacing around headings
    text = text.replace(/(#{1,6}\s.+)\n/g, '\n$1\n\n');

    // Ensure lists have proper spacing
    text = text.replace(/^(\s*[-*+]\s)/gm, '\n$1');

    return text;
  }, [content]);

  return (
    <div className="markdown-content">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={components}
      >
        {enhancedContent}
      </ReactMarkdown>
    </div>
  );
}
