/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/**/*.{js,ts,jsx,tsx,mdx}', './components/**/*.{js,ts,jsx,tsx,mdx}', './lib/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      boxShadow: {
        glow: '0 0 0 1px rgba(148, 163, 184, 0.15), 0 10px 30px rgba(15, 23, 42, 0.4)',
      },
      colors: {
        slate: {
          950: '#020817',
        },
      },
    },
  },
  plugins: [],
};
