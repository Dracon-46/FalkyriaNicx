// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { AutonomyState } from '../lib/historico';

const api = vi.hoisted(() => ({
  obterAutonomia: vi.fn(),
  salvarAutonomia: vi.fn(),
}));

vi.mock('../lib/historico', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/historico')>()),
  ...api,
}));

import { AutonomySettings } from '../components/Settings/AutonomySettings';

const state: AutonomyState = {
  nivel: 'assistido',
  niveis: [
    { nivel: 'observador', liberado: ['leitura'] },
    { nivel: 'assistido', liberado: ['leitura', 'leve'] },
    { nivel: 'autonomo', liberado: ['leitura', 'leve', 'moderado'] },
  ],
  riscos: ['leitura', 'leve', 'moderado', 'alto'],
};

// Os testes rodam com os textos em português (src/i18n/test-setup.ts).
describe('AutonomySettings', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('mostra o nível atual e o que passa sem perguntar', async () => {
    api.obterAutonomia.mockResolvedValue(state);
    render(<AutonomySettings onSaved={() => {}} />);

    const assistido = await screen.findByTestId('autonomy-assistido');
    await waitFor(() => expect(assistido.getAttribute('aria-checked')).toBe('true'));
    expect(screen.getByTestId('autonomy-observador').getAttribute('aria-checked')).toBe('false');
    expect(assistido.textContent).toContain('Assistido');
    expect(assistido.textContent).toContain('padrão');

    expect(screen.getByTestId('autonomy-cell-assistido-leve').getAttribute('data-free')).toBe('true');
    expect(screen.getByTestId('autonomy-cell-assistido-moderado').getAttribute('data-free')).toBe('false');
    expect(screen.getByTestId('autonomy-cell-autonomo-moderado').getAttribute('data-free')).toBe('true');
    expect(screen.getByTestId('autonomy-cell-autonomo-alto').getAttribute('data-free')).toBe('false');
    expect(screen.getByText(/sempre pedem "confirmo"/)).toBeTruthy();
  });

  it('salva ao trocar de nível', async () => {
    api.obterAutonomia.mockResolvedValue(state);
    api.salvarAutonomia.mockResolvedValue({ ...state, nivel: 'autonomo' });
    const onSaved = vi.fn();
    render(<AutonomySettings onSaved={onSaved} />);

    const autonomo = (await screen.findByTestId('autonomy-autonomo')) as HTMLButtonElement;
    await waitFor(() => expect(autonomo.disabled).toBe(false));
    fireEvent.click(autonomo);
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(api.salvarAutonomia).toHaveBeenCalledWith('autonomo');
    expect(screen.getByTestId('autonomy-autonomo').getAttribute('aria-checked')).toBe('true');
    expect(screen.getByTestId('autonomy-assistido').getAttribute('aria-checked')).toBe('false');

    // O nível já escolhido não salva de novo.
    fireEvent.click(screen.getByTestId('autonomy-autonomo'));
    expect(api.salvarAutonomia).toHaveBeenCalledTimes(1);
  });

  it('erro ao salvar aparece e mantém o nível', async () => {
    api.obterAutonomia.mockResolvedValue(state);
    api.salvarAutonomia.mockRejectedValue(new Error('Não consegui salvar a autonomia. Tente de novo.'));
    render(<AutonomySettings onSaved={() => {}} />);

    const observador = (await screen.findByTestId('autonomy-observador')) as HTMLButtonElement;
    await waitFor(() => expect(observador.disabled).toBe(false));
    fireEvent.click(observador);
    expect(await screen.findByText('Não consegui salvar a autonomia. Tente de novo.')).toBeTruthy();
    expect(screen.getByTestId('autonomy-assistido').getAttribute('aria-checked')).toBe('true');
  });

  it('servidor antigo: avisa para reiniciar', async () => {
    api.obterAutonomia.mockRejectedValue(new Error('Reinicie o servidor do Nicx para usar o histórico e a autonomia.'));
    render(<AutonomySettings onSaved={() => {}} />);
    expect(await screen.findByText(/Reinicie o servidor do Nicx/)).toBeTruthy();
    expect((screen.getByTestId('autonomy-assistido') as HTMLButtonElement).disabled).toBe(true);
  });
});
