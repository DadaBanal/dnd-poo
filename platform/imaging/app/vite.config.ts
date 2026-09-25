// Builds the page into dist/: hashed files, no source maps, nothing fetched
// from anywhere but this origin at run time.
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  base: '/pmc/',
  root: 'src/web',
  build: {
    outDir: '../../dist',
    emptyOutDir: true,
    sourcemap: false,
    // Every asset is a file of its own, so the content security policy
    // never has to allow data: scripts or styles.
    assetsInlineLimit: 0,
    rollupOptions: {
      output: {
        // The page's own code apart from its libraries, each in a file named
        // by its content: a change to the page costs a PC only the page's
        // file (the libraries' files keep their names, and their year in the
        // cache, until a library changes), and a browser fetches the parts at
        // once over HTTP/2.
        manualChunks(id) {
          if (!id.includes('/node_modules/')) return undefined;
          if (/\/node_modules\/(react|react-dom|scheduler)\//.test(id)) return 'react';
          if (/\/node_modules\/(react-aria|react-aria-components|@react-aria|@react-stately|@react-types|@internationalized|use-sync-external-store|@swc\/helpers|clsx|client-only)\//.test(id)) return 'aria';
          if (id.includes('/node_modules/@tanstack/')) return 'tanstack';
          return 'vendor';
        },
      },
    },
  },
  plugins: [react(), tailwindcss()],
});
