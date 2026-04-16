/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,jsx,ts,tsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        // ✅ These are now usable as Tailwind classes: font-outfit, font-grotesk
        outfit:  ['Outfit', 'sans-serif'],
        grotesk: ['Space Grotesk', 'sans-serif'],
      },
      colors: {
        flow:    '#00d4aa',
        flow2:   '#00b8ff',
        flow3:   '#7c3aed',
        ink:     '#05080f',
        ink2:    '#0b1120',
        surface: '#141d2e',
        surface2:'#1a2540',
      },
      backdropBlur: {
        '2xl': '40px',
      },
    },
  },
  plugins: [],
}
 