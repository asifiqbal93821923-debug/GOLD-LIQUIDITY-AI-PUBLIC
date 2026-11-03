import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  // Relative asset paths allow the same build to run at the GitHub project Pages URL.
  base: './',
  plugins: [react()],
  server: { proxy: { '/api': { target: 'http://127.0.0.1:8765', changeOrigin: true } } },
});
