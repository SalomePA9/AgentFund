/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      // Colors matching UI/UX guidelines (Superior template benchmark)
      colors: {
        background: {
          DEFAULT: '#0A0A0B',
          secondary: '#111113',
          tertiary: '#18181B',
          hover: '#1F1F23',
        },
        border: {
          DEFAULT: '#27272A',
          secondary: '#3F3F46',
        },
        accent: {
          DEFAULT: '#3B82F6',
          hover: '#2563EB',
          muted: '#1D4ED8',
          subtle: 'rgba(59, 130, 246, 0.1)',
        },
        success: {
          DEFAULT: '#22C55E',
          subtle: 'rgba(34, 197, 94, 0.1)',
        },
        error: {
          DEFAULT: '#EF4444',
          subtle: 'rgba(239, 68, 68, 0.1)',
        },
        warning: {
          DEFAULT: '#F59E0B',
          subtle: 'rgba(245, 158, 11, 0.1)',
        },
      },
      // Typography
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'SF Mono', 'Fira Code', 'monospace'],
      },
      // Animations
      animation: {
        'fade-in': 'fadeIn 200ms ease-out',
        'slide-up': 'slideUp 300ms ease-out',
        'scale-in': 'scaleIn 200ms ease-out',
        'shimmer': 'shimmer 1.5s infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      // Spacing
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
        '112': '28rem',
        '128': '32rem',
      },
      // Border radius
      borderRadius: {
        '4xl': '2rem',
      },
      // Backdrop blur
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [],
};
