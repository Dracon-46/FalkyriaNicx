// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  fetchDailySummaryConfig: vi.fn(),
  updateDailySummaryConfig: vi.fn(),
  fetchDailySummary: vi.fn(),
}));

vi.mock('../lib/resumo', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/resumo')>()),
  ...api,
}));

import { DailySummarySettings } from '../components/Settings/DailySummarySettings';

const base = {
  ativo: false,
  hora: '18:00',
  falar: true,
  notificar: true,
  dias: ['seg', 'ter', 'qua', 'qui', 'sex'],
  opcoes_dias: ['seg', 'ter', 'qua', 'qui', 'sex', 'sab', 'dom'],
  ultimo_envio: null,
};

const resumo = {
  dia: '2026-10-30',
  idioma: 'pt-BR',
  texto: 'Resumo do seu dia. Amanhã você tem: dentista às 9h.',
  texto_pendente: 'Nada ficou pendente hoje.',
  refinado: false,
};

// Os testes rodam com os textos em português (src/i18n/test-setup.ts).
describe('DailySummarySettings', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('mostra a config e liga o resumo automático', async () => {
    api.fetchDailySummaryConfig.mockResolvedValue(base);
    api.updateDailySummaryConfig.mockResolvedValue({ ...base, ativo: true });
    const onSaved = vi.fn();
    render(<DailySummarySettings onSaved={onSaved} />);

    const ativo = await screen.findByTestId('summary-enabled');
    await waitFor(() => expect((ativo as HTMLButtonElement).disabled).toBe(false));
    expect(ativo.getAttribute('aria-checked')).toBe('false');
    expect((screen.getByTestId('summary-time') as HTMLInputElement).value).toBe('18:00');
    expect(screen.getByTestId('summary-speak').getAttribute('aria-checked')).toBe('true');
    expect(screen.getByTestId('summary-day-sex').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('summary-day-sab').getAttribute('aria-pressed')).toBe('false');
    expect(screen.getByText('Sáb')).toBeTruthy();

    fireEvent.click(ativo);
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(api.updateDailySummaryConfig).toHaveBeenCalledWith({ ativo: true });
    expect(screen.getByTestId('summary-enabled').getAttribute('aria-checked')).toBe('true');
  });

  it('troca a hora e os dias', async () => {
    api.fetchDailySummaryConfig.mockResolvedValue(base);
    api.updateDailySummaryConfig.mockImplementation(async (update) => ({ ...base, ...update }));
    render(<DailySummarySettings onSaved={() => {}} />);

    const hora = (await screen.findByTestId('summary-time')) as HTMLInputElement;
    await waitFor(() => expect(hora.disabled).toBe(false));
    fireEvent.change(hora, { target: { value: '07:30' } });
    await waitFor(() => expect(api.updateDailySummaryConfig).toHaveBeenCalledWith({ hora: '07:30' }));

    const sabado = screen.getByTestId('summary-day-sab') as HTMLButtonElement;
    await waitFor(() => expect(sabado.disabled).toBe(false));
    fireEvent.click(sabado);
    await waitFor(() =>
      expect(api.updateDailySummaryConfig).toHaveBeenCalledWith({
        dias: ['seg', 'ter', 'qua', 'qui', 'sex', 'sab'],
      }),
    );
    await waitFor(() => expect(screen.getByTestId('summary-day-sab').getAttribute('aria-pressed')).toBe('true'));

    fireEvent.click(screen.getByTestId('summary-day-seg'));
    await waitFor(() =>
      expect(api.updateDailySummaryConfig).toHaveBeenLastCalledWith({
        dias: ['ter', 'qua', 'qui', 'sex', 'sab'],
      }),
    );
  });

  it('"Ver resumo de hoje" mostra o texto e oferece deixar mais natural', async () => {
    api.fetchDailySummaryConfig.mockResolvedValue({ ...base, ultimo_envio: '2026-10-29' });
    api.fetchDailySummary.mockResolvedValueOnce(resumo).mockResolvedValueOnce({
      ...resumo,
      texto: 'Hoje foi tranquilo; amanhã tem dentista às 9h.',
      refinado: true,
    });
    render(<DailySummarySettings onSaved={() => {}} />);

    expect(await screen.findByText(/Último resumo automático: 2026-10-29/)).toBeTruthy();
    expect(screen.queryByTestId('summary-refine')).toBeNull();
    fireEvent.click(screen.getByText('Ver resumo de hoje'));
    expect(await screen.findByText(resumo.texto)).toBeTruthy();
    expect(api.fetchDailySummary).toHaveBeenCalledWith('pt-BR', false);

    fireEvent.click(screen.getByTestId('summary-refine'));
    expect(await screen.findByText('Hoje foi tranquilo; amanhã tem dentista às 9h.')).toBeTruthy();
    expect(api.fetchDailySummary).toHaveBeenLastCalledWith('pt-BR', true);
  });

  it('servidor antigo: avisa para reiniciar', async () => {
    api.fetchDailySummaryConfig.mockRejectedValue(new Error('Reinicie o servidor do Nicx para usar o resumo do dia'));
    render(<DailySummarySettings onSaved={() => {}} />);
    expect(await screen.findByText(/Reinicie o servidor do Nicx/)).toBeTruthy();
    expect((screen.getByTestId('summary-enabled') as HTMLButtonElement).disabled).toBe(true);
  });
});
