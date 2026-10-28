import { defineConfig, mergeConfig } from 'vitest/config';
import viteConfig from './vite.config';

// Os testes usam a mesma configuração do app e já começam com os textos
// em português carregados (componentes com useTranslation).
export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      setupFiles: ['./src/i18n/test-setup.ts'],
    },
  }),
);
