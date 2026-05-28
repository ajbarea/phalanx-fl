import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, path.resolve(__dirname, '..'), '');

  return {
    plugins: [react()],
    envDir: '../',
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
        '@components': path.resolve(__dirname, './src/components'),
        '@hooks': path.resolve(__dirname, './src/hooks'),
        '@api': path.resolve(__dirname, './src/api'),
        '@utils': path.resolve(__dirname, './src/utils'),
        '@constants': path.resolve(__dirname, './src/constants'),
        '@contexts': path.resolve(__dirname, './src/contexts'),
        '@pages': path.resolve(__dirname, './src/pages'),
      },
    },
    server: {
      host: '0.0.0.0',
      allowedHosts: 'all',
      watch: {
        usePolling: true,
      },
      hmr: {
        host: 'localhost',
        port: 5173,
        protocol: 'ws',
      },
      proxy: {
        '/docs': {
          target: env.VITE_DOCS_PROXY_TARGET || 'http://127.0.0.1:8080',
          changeOrigin: true,
          rewrite: path => path.replace(/^\/docs/, ''),
        },
        '/api': {
          target: env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000',
          changeOrigin: true,
          ws: true,
          configure: proxy => {
            proxy.on('proxyRes', proxyRes => {
              // Disable buffering for SSE (text/event-stream) responses to ensure immediate event delivery
              const contentType = proxyRes.headers['content-type'] || '';
              if (contentType.includes('text/event-stream')) {
                proxyRes.headers['x-accel-buffering'] = 'no';
                proxyRes.headers['cache-control'] = 'no-cache';
              }
            });
          },
        },
      },
    },
    base: '/',
    build: {
      // The shared chunk (react + router + query) is legitimately ~0.9MB; the leaf splits
      // below are the real caching win. Bump the advisory limit rather than over-split.
      chunkSizeWarningLimit: 1100,
      rollupOptions: {
        output: {
          // research(2026-05): split only *leaf* vendor libs (charts/terminal/assistant/
          // bootstrap) that depend on react one-way into cacheable chunks, so an app-only
          // change no longer busts the whole ~1.7MB bundle's cache. React core is left in the
          // shared chunk on purpose — pulling it into its own chunk produced a circular
          // vendor<->vendor-react chunk. Vite 8 replaces manualChunks with `codeSplitting`.
          manualChunks(id) {
            if (!id.includes('node_modules')) return undefined;
            if (id.includes('recharts') || id.includes('/d3-')) return 'vendor-charts';
            if (id.includes('@xterm')) return 'vendor-xterm';
            if (id.includes('@assistant-ui') || id.includes('react-markdown'))
              return 'vendor-assistant';
            if (id.includes('react-bootstrap') || id.includes('/bootstrap/'))
              return 'vendor-bootstrap';
            return 'vendor';
          },
        },
      },
    },
  };
});
