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
  },
  plugins: [react(), tailwindcss()],
});
