import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../lib/store', () => ({ useAppStore: vi.fn() }));

import { MemoryStatusRow } from './SettingsPage';

// Os testes rodam com os textos em português (src/i18n/test-setup.ts).
describe('Settings memory status', () => {
  it('shows the failure detail and a Retry action, then the recovered count', () => {
    const onRetry = vi.fn();
    const failed = renderToStaticMarkup(
      <MemoryStatusRow
        status={{ kind: 'error', message: 'Missing Authorization header (HTTP 401)' }}
        onRetry={onRetry}
      />,
    );
    const recovered = renderToStaticMarkup(
      <MemoryStatusRow
        status={{ kind: 'ready', stats: { backend: 'sqlite', entries: 3 } }}
        onRetry={onRetry}
      />,
    );

    expect(failed).toContain('Missing Authorization header (HTTP 401)');
    expect(failed).toContain('Tentar de novo');
    expect(failed).toContain('Indisponível');
    expect(failed).not.toContain('Unable to reach memory service');
    expect(recovered).toContain('sqlite — itens guardados: 3');
    expect(recovered).not.toContain('Tentar de novo');
    expect(recovered).not.toContain('Missing Authorization header');
  });

  it('does not present an unconfigured backend as connected', () => {
    const html = renderToStaticMarkup(
      <MemoryStatusRow
        status={{ kind: 'ready', stats: { backend: 'none', entries: 0, status: 'not_configured' } }}
        onRetry={vi.fn()}
      />,
    );

    expect(html).toContain('A memória não está configurada');
    expect(html).toContain('Não configurada');
    expect(html).not.toContain('Itens: 0');
  });
});
