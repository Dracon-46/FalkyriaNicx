// Painel Falkyria publicado na web (`npm run build:painel`): só a página do
// painel, sem o resto do app e sem depender do servidor local do Nicx.
import './lib/polyfills';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { ErrorBoundary } from './components/ErrorBoundary';
import { PainelPage } from './pages/PainelPage';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <PainelPage />
    </ErrorBoundary>
  </StrictMode>,
);
