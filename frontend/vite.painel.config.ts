// Build do Painel Falkyria como site estático (GitHub Pages).
// Uso: npm run build:painel  ->  dist-painel/
import path from 'path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// Projeto Supabase da Falkyria. A chave é a pública (publishable), a mesma do
// app; quem decide o que cada um lê é o RLS do banco.
process.env.VITE_PAINEL_SUPABASE_URL ||= 'https://xcazupxhoeoogcksymzg.supabase.co';
process.env.VITE_PAINEL_SUPABASE_KEY ||= 'sb_publishable_udh4J44z3XxDaXlGTYbaIA_iT9NcTQD';

export default defineConfig({
  root: path.resolve(import.meta.dirname, 'painel'),
  publicDir: path.resolve(import.meta.dirname, 'public'),
  envDir: import.meta.dirname,
  // Caminhos relativos: funciona em qualquer subpasta do Pages.
  base: './',
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  plugins: [react(), tailwindcss()],
  build: {
    outDir: path.resolve(import.meta.dirname, 'dist-painel'),
    emptyOutDir: true,
    target: ['es2020', 'edge88', 'firefox78', 'chrome87', 'safari14'],
  },
});
