/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        sentinel: {
          dark: '#0F172A',
          navy: '#1E293B',
          teal: '#0D9488',
          tealHover: '#0F766E',
          emerald: '#10B981',
          canvas: '#F8FAFC',
          card: '#FFFFFF',
          border: '#E2E8F0',
          muted: '#64748B',
          warning: '#F59E0B',
          danger: '#EF4444',
          alertHot: '#DC2626'
        }
      }
    },
  },
  plugins: [],
}
