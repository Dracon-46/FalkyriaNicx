// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  fetchScreenContextConfig: vi.fn(),
  updateScreenContextConfig: vi.fn(),
}));

vi.mock('../lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/api')>()),
  ...api,
}));

import { ContextSettings } from '../components/Settings/ContextSettings';

const base = {
  ativo: true,
  copiar_selecao: false,
  max_caracteres: 20000,
  limites: [5000, 10000, 20000, 40000],
  suportado: true,
};

// Os testes rodam com os textos em português (src/i18n/test-setup.ts).
describe('ContextSettings', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('mostra a config e liga "copiar a seleção"', async () => {
    api.fetchScreenContextConfig.mockResolvedValue(base);
    api.updateScreenContextConfig.mockResolvedValue({ ...base, copiar_selecao: true });
    const onSaved = vi.fn();
    render(<ContextSettings onSaved={onSaved} />);

    const ativo = await screen.findByTestId('context-enabled');
    await waitFor(() => expect((ativo as HTMLButtonElement).disabled).toBe(false));
    expect(ativo.getAttribute('aria-checked')).toBe('true');
    const copiar = screen.getByTestId('context-copy');
    expect(copiar.getAttribute('aria-checked')).toBe('false');
    expect(screen.getByText(/Janelas de senha e de banco não são lidas/)).toBeTruthy();

    fireEvent.click(copiar);
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(api.updateScreenContextConfig).toHaveBeenCalledWith({ copiar_selecao: true });
    expect(screen.getByTestId('context-copy').getAttribute('aria-checked')).toBe('true');
  });

  it('troca o limite de caracteres', async () => {
    api.fetchScreenContextConfig.mockResolvedValue(base);
    api.updateScreenContextConfig.mockResolvedValue({ ...base, max_caracteres: 10000 });
    render(<ContextSettings onSaved={() => {}} />);

    const select = (await screen.findByTestId('context-limit')) as HTMLSelectElement;
    await waitFor(() => expect(select.disabled).toBe(false));
    fireEvent.change(select, { target: { value: '10000' } });
    await waitFor(() => expect(api.updateScreenContextConfig).toHaveBeenCalledWith({ max_caracteres: 10000 }));
  });

  it('desligado: as outras opções ficam travadas', async () => {
    api.fetchScreenContextConfig.mockResolvedValue({ ...base, ativo: false });
    render(<ContextSettings onSaved={() => {}} />);
    const ativo = await screen.findByTestId('context-enabled');
    await waitFor(() => expect(ativo.getAttribute('aria-checked')).toBe('false'));
    expect((screen.getByTestId('context-copy') as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByTestId('context-limit') as HTMLSelectElement).disabled).toBe(true);
  });

  it('fora do Windows avisa', async () => {
    api.fetchScreenContextConfig.mockResolvedValue({ ...base, suportado: false });
    render(<ContextSettings onSaved={() => {}} />);
    expect(await screen.findByText(/só são lidas no Windows/)).toBeTruthy();
  });
});
