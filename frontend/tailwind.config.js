/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        sqa: {
          navy: '#0a1628',
          'navy-light': '#111d35',
          gold: '#f5a623',
          'gold-dark': '#d4891a',
          'gold-light': '#f7b84e',
          card: '#162040',
          border: '#1e3a5f',
        },
      },
    },
  },
  plugins: [],
}
