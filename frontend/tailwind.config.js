/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Fira Code"', 'Menlo', 'monospace'],
      },
      colors: {
        surface: {
          base:    '#020617',
          panel:   '#070d1a',
          card:    '#0d1526',
          elevated:'#111f35',
          hover:   '#162540',
        },
      },
      animation: {
        'shimmer':     'shimmer 1.8s linear infinite',
        'fade-in':     'fadeIn 0.2s ease-out',
        'slide-up':    'slideUp 0.22s cubic-bezier(0.16, 1, 0.3, 1)',
        'scale-in':    'scaleIn 0.18s cubic-bezier(0.16, 1, 0.3, 1)',
        'spin-slow':   'spin 2.4s linear infinite',
        'pulse-soft':  'pulseSoft 2s ease-in-out infinite',
      },
      keyframes: {
        shimmer: {
          '0%':   { backgroundPosition: '-400% 0' },
          '100%': { backgroundPosition: '400% 0' },
        },
        fadeIn: {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%':   { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        scaleIn: {
          '0%':   { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%':      { opacity: '0.5' },
        },
      },
      boxShadow: {
        'card':     '0 1px 3px rgba(0,0,0,0.5), 0 1px 2px rgba(0,0,0,0.4)',
        'elevated': '0 4px 24px rgba(0,0,0,0.6), 0 1px 4px rgba(0,0,0,0.4)',
        'glow-sm':  '0 0 12px rgba(99,102,241,0.2)',
        'glow':     '0 0 24px rgba(99,102,241,0.25)',
        'inner-sm': 'inset 0 1px 0 rgba(255,255,255,0.04)',
      },
      backdropBlur: {
        xs: '4px',
      },
    },
  },
  plugins: [],
}
