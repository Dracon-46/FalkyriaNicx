// Must stay the first import: fills in crypto.randomUUID before any module uses it.
import './lib/polyfills';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router';
import { ErrorBoundary } from './components/ErrorBoundary';
import { initApiBase } from './lib/api';
import { initAnalytics } from './lib/analytics';
import './index.css';
import { DEFAULT_LANGUAGE, setLanguage } from './i18n';

// "localhost" and "127.0.0.1" are different origins with separate storage, so
// settings and conversations would seem to vanish when switching between them.
// Always use 127.0.0.1, the address `nicx gui` and `nicx start` open.
if (window.location.hostname === 'localhost') {
  const url = new URL(window.location.href);
  url.hostname = '127.0.0.1';
  window.location.replace(url.toString());
}

function applyTheme() {
  try {
    const raw = localStorage.getItem('nicx-settings');
    const settings = raw ? JSON.parse(raw) : {};
    const theme = settings.theme || 'system';
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
      document.documentElement.classList.remove('light');
    } else if (theme === 'light') {
      document.documentElement.classList.add('light');
      document.documentElement.classList.remove('dark');
    }
  } catch { /* use system default */ }
}

/** The floating mascot ("Nicx, ligar") loads only what it needs. */
const FLOATING = window.location.pathname.replace(/\/+$/, '') === '/flutuante';

if (FLOATING) {
  document.documentElement.classList.add('dark');
  document.documentElement.classList.remove('light');
} else {
  applyTheme();
}

// Fetch the API base URL from the Tauri backend before rendering.
// This ensures NICX_PORT is defined in one place (the Rust backend).
// In non-Tauri environments this is a no-op.
/** Idioma salvo nas configurações (o mesmo que applyTheme lê). */
function savedLanguage(): string {
  try {
    const raw = localStorage.getItem('nicx-settings');
    return (raw && JSON.parse(raw).language) || DEFAULT_LANGUAGE;
  } catch {
    return DEFAULT_LANGUAGE;
  }
}

Promise.all([initApiBase(), setLanguage(savedLanguage()).catch(() => undefined)]).finally(async () => {
  const root = createRoot(document.getElementById('root')!);
  if (FLOATING) {
    const { default: FloatingPage } = await import('./pages/FloatingPage');
    root.render(
      <StrictMode>
        <ErrorBoundary>
          <FloatingPage />
        </ErrorBoundary>
      </StrictMode>,
    );
    return;
  }

  // Kick off analytics init in the background — it's never awaited so
  // a slow/failed identity fetch never delays UI render.
  void initAnalytics();

  const { default: App } = await import('./App');
  root.render(
    <StrictMode>
      <ErrorBoundary>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </ErrorBoundary>
    </StrictMode>,
  );
});
