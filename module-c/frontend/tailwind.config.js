/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: '#2c6fce',
        'primary-light': '#4a8fe7',
        gold: '#c9a84c',
        'gold-light': '#e0c56e',
        'bg-sidebar': '#0d1a2d',
        'bg-header': '#111d32',
        'bg-content': '#f0f2f5',
        'card-bg': '#ffffff',
        'text-primary': '#1a1a2e',
        'text-secondary': '#6b7280',
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          'Roboto',
          '"Helvetica Neue"',
          'Arial',
          '"Microsoft YaHei"',
          'sans-serif',
        ],
      },
    },
  },
  plugins: [],
  corePlugins: {
    preflight: false, // 与 antd 兼容
  },
};
