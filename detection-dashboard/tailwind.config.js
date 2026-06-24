/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        ueba: {
          bg: {
            DEFAULT: '#0f172a', // slate-900
            deep: '#020617',    // slate-950
          },
          card: '#1e293b',      // slate-800
          cardhover: '#334155', // slate-700
          border: '#334155',    // slate-700
          text: {
            primary: '#f1f5f9',   // slate-100
            secondary: '#cbd5e1', // slate-300
            muted: '#64748b',     // slate-500
          },
          accent: {
            green: '#10b981',    // emerald-500
            red: '#ef4444',      // red-500
            blue: '#3b82f6',     // blue-500
            yellow: '#eab308',   // yellow-500
            purple: '#a855f7',   // purple-500
          },
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};
