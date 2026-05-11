import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { TanStackRouterVite } from '@tanstack/router-plugin/vite';

const here = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [
    // Tailwind v4: the Vite plugin is the recommended integration. Reads the
    // @theme block in @baseflo/ui/tokens.css to generate utilities. No
    // tailwind.config.ts, no postcss.config.cjs.
    tailwindcss(),
    TanStackRouterVite({
      routesDirectory: path.resolve(here, 'src/routes'),
      generatedRouteTree: path.resolve(here, 'src/routeTree.gen.ts'),
      autoCodeSplitting: true,
    }),
    react(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(here, 'src'),
    },
  },
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
  build: {
    sourcemap: true,
    target: 'es2022',
    rollupOptions: {
      output: {
        manualChunks: {
          'tanstack-vendor': ['@tanstack/react-query', '@tanstack/react-router'],
        },
      },
    },
  },
});
