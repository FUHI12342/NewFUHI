/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './booking/templates/**/*.html',
  ],
  theme: {
    extend: {
      colors: {
        'salon-brown': '#8c876c',
        'salon-beige': '#f1f0ec',
        'salon-dark': '#333333',
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
