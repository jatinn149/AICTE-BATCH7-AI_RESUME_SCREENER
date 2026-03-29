/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}"
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Manrope', 'system-ui', '-apple-system', 'sans-serif'],
        display: ['Space Grotesk', 'Manrope', 'sans-serif'],
        mono: ['Fira Code', 'monospace'],
      },
      colors: {
        brand: {
          50: '#eff6ff',
          100: '#dbeafe',
          500: '#0b5fff',
          600: '#0046d7',
          700: '#0036a6',
        },
        teal: {
          500: '#0f766e',
          600: '#115e59',
        },
      },
      boxShadow: {
        soft: '0 10px 35px -24px rgba(15, 23, 42, 0.55)',
        raised: '0 20px 40px -28px rgba(15, 23, 42, 0.6)',
      },
      animation: {
        'slide-in': 'slideIn 0.45s ease-out',
        'fade-in': 'fadeIn 0.45s ease-out',
      },
      keyframes: {
        slideIn: {
          'from': { opacity: '0', transform: 'translateY(20px)' },
          'to': { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          'from': { opacity: '0' },
          'to': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
};
