/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './booking/templates/**/*.html',
  ],
  theme: {
    extend: {
      colors: {
        'salon-brown': 'var(--color-primary, #8c876c)',
        'salon-beige': 'var(--color-secondary, #f1f0ec)',
        'salon-dark': 'var(--color-text, #333333)',
        'salon-accent': 'var(--color-accent, #b8860b)',
      },
      fontFamily: {
        'jp': [
          '"ヒラギノ角ゴ Pro W3"',
          '"Hiragino Kaku Gothic Pro"',
          '"メイリオ"',
          'Meiryo',
          'sans-serif',
        ],
      },
    },
  },
  plugins: [],
}
