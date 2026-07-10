import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  base: '/static/react/',
  build: { outDir: '../static/react', emptyOutDir: true },
});
