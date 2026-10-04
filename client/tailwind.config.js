/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      boxShadow: {
        glow: '0 0 30px rgba(129, 140, 248, 0.35)',
      },
      colors: {
        night: '#050816',
        panel: '#0f172a',
      },
      backgroundImage: {
        'mesh-grid': 'radial-gradient(circle at top, rgba(99,102,241,0.2), transparent 35%), linear-gradient(rgba(15,23,42,0.8), rgba(2,6,23,1))',
      },
    },
  },
  plugins: [],
}

