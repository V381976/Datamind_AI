/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/**/*.{js,ts,jsx,tsx,mdx}', './components/**/*.{js,ts,jsx,tsx,mdx}', './lib/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        'chatgpt': {
          'bg': '#0a0a1a',
          'sidebar': '#0f172a',
          'input': '#1e293b',
          'green': '#6366f1',
          'green-light': '#818cf8',
          'text': '#e2e8f0',
          'text-dim': '#94a3b8',
          'text-dimmer': '#64748b',
          'border': '#1e293b',
        },
        'accent': {
          'indigo': '#6366f1',
          'purple': '#8b5cf6',
          'violet': '#a855f7',
          'blue': '#3b82f6',
        },
      },
      boxShadow: {
        'glow': '0 0 0 1px rgba(99, 102, 241, 0.15), 0 10px 30px rgba(15, 23, 42, 0.4)',
        'glow-lg': '0 0 40px rgba(99, 102, 241, 0.2)',
        'glow-xl': '0 0 60px rgba(99, 102, 241, 0.3)',
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic': 'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
        'gradient-premium': 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%)',
      },
      animation: {
        'float': 'float 6s ease-in-out infinite',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        glow: {
          '0%': { boxShadow: '0 0 20px rgba(99, 102, 241, 0.3)' },
          '100%': { boxShadow: '0 0 40px rgba(99, 102, 241, 0.5)' },
        },
      },
      fontFamily: {
        sans: ['Inter', 'Söhne', 'Segoe UI', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
};
