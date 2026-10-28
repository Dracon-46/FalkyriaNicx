import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';

describe('desktop cloud provider settings', () => {
  it('offers Atlas Cloud key storage alongside its provider status', async () => {
    vi.stubGlobal('localStorage', { getItem: () => null });
    vi.stubGlobal('window', { __TAURI_INTERNALS__: {} });
    const { SettingsPage } = await import('./SettingsPage');
    const html = renderToStaticMarkup(<SettingsPage />);

    expect(html).toContain('Atlas Cloud');
    // Placeholder em português (os testes carregam o pt-BR).
    const atlasKeyInput = html.match(/<input[^>]*placeholder="Chave de API do Atlas Cloud"[^>]*>/)?.[0];
    expect(atlasKeyInput).toBeDefined();
    expect(atlasKeyInput).not.toContain('disabled');
    vi.unstubAllGlobals();
  });
});
