/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        bull: '#00C087',
        bear: '#FF4D4F',
        primary: '#1890FF',
        background: {
          DEFAULT: '#0B0E11',
          subtle: '#141414',
          card: '#1F2329',
        },
      },
      boxShadow: {
        card: '0 8px 24px rgba(0, 0, 0, 0.35)',
      },
    },
  },
  plugins: [],
}
