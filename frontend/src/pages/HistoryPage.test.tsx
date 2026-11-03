// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Activity } from '../lib/historico';

const api = vi.hoisted(() => ({
  listarHistorico: vi.fn(),
  desfazerAtividade: vi.fn(),
  verificarIntegridade: vi.fn(),
}));

vi.mock('../lib/historico', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/historico')>()),
  ...api,
}));

import { HistoryPage } from './HistoryPage';

/** "AAAA-MM-DDTHH:MM:SS" local, `days` dias atrás. */
function local(days: number, time: string): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${time}`;
}

function activity(over: Partial<Activity>): Activity {
  return {
    id: 1,
    quando: local(0, '14:05:11'),
    tipo: 'nota',
    titulo: 'Anotou: comprar pão',
    origem: 'chat',
    resultado: 'ok',
    nivel: '',
    detalhe: {},
    desfazivel: false,
    desfeito_em: null,
    ...over,
  };
}

const nota = activity({ id: 3, desfazivel: true });
const lembrete = activity({ id: 2, quando: local(1, '09:30:00'), tipo: 'lembrete', titulo: 'Lembrete: dentista', origem: 'voz' });
const antiga = activity({
  id: 1,
  quando: local(1, '08:00:00'),
  tipo: 'lembrete',
  titulo: 'Lembrete: reunião',
  desfeito_em: local(1, '08:10:00'),
});

const ferramenta = activity({
  id: 9,
  tipo: 'ferramenta',
  titulo: 'Escreveu o arquivo notas.txt',
  origem: 'agente',
  resultado: 'bloqueado',
  nivel: 'assistido',
  detalhe: {
    ferramenta: 'file_write',
    argumentos: { caminho: 'C:\\notas.txt', conteudo: 'oi' },
    resposta: 'Pedi "confirmo" antes de escrever.',
    risco: 'moderado',
  },
});

// Os testes rodam com os textos em português (src/i18n/test-setup.ts).
describe('HistoryPage', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('agrupa as atividades por dia', async () => {
    api.listarHistorico.mockResolvedValue({ itens: [nota, lembrete, antiga], mais: false });
    render(<HistoryPage />);

    const lista = await screen.findByTestId('history-list');
    expect(lista.textContent).toContain('Hoje');
    expect(lista.textContent).toContain('Ontem');
    expect(lista.textContent).toContain('Anotou: comprar pão');
    expect(screen.getByTestId('history-item-3').textContent).toContain('14:05');
    expect(screen.getByTestId('history-item-2').textContent).toContain('Voz');
    expect(screen.getByTestId('history-item-1').textContent).toContain('Desfeito');
    expect(screen.getByTestId('history-undo-3')).toBeTruthy();
    expect(screen.queryByTestId('history-undo-2')).toBeNull();
    expect(screen.queryByTestId('history-undo-1')).toBeNull();
    expect(api.listarHistorico).toHaveBeenCalledWith(expect.objectContaining({ tipos: [], limite: 50 }));
  });

  it('desfaz, mostra a mensagem e recarrega', async () => {
    api.listarHistorico
      .mockResolvedValueOnce({ itens: [nota], mais: false })
      .mockResolvedValue({ itens: [{ ...nota, desfeito_em: local(0, '14:06:00') }], mais: false });
    api.desfazerAtividade.mockResolvedValue({ ok: true, mensagem: 'Pronto, apaguei a anotação.' });
    render(<HistoryPage />);

    fireEvent.click(await screen.findByTestId('history-undo-3'));
    await waitFor(() => expect(api.desfazerAtividade).toHaveBeenCalledWith(3, 'pt-BR'));
    expect((await screen.findByTestId('history-notice')).textContent).toContain('Pronto, apaguei a anotação.');
    await waitFor(() => expect(screen.getByTestId('history-item-3').textContent).toContain('Desfeito'));
    expect(api.listarHistorico).toHaveBeenCalledTimes(2);
  });

  it('filtra por tipo e busca depois de uma pausa', async () => {
    api.listarHistorico.mockResolvedValue({ itens: [nota], mais: false });
    render(<HistoryPage />);
    await screen.findByTestId('history-list');

    fireEvent.click(screen.getByTestId('history-type-nota'));
    await waitFor(() =>
      expect(api.listarHistorico).toHaveBeenLastCalledWith(expect.objectContaining({ tipos: ['nota'] })),
    );
    expect(screen.getByTestId('history-type-nota').getAttribute('aria-pressed')).toBe('true');

    fireEvent.change(screen.getByTestId('history-search'), { target: { value: 'pão' } });
    await waitFor(() =>
      expect(api.listarHistorico).toHaveBeenLastCalledWith(expect.objectContaining({ busca: 'pão', tipos: ['nota'] })),
    );
  });

  it('carrega mais a partir da última atividade', async () => {
    api.listarHistorico
      .mockResolvedValueOnce({ itens: [nota, lembrete], mais: true })
      .mockResolvedValueOnce({ itens: [antiga], mais: false });
    render(<HistoryPage />);

    fireEvent.click(await screen.findByTestId('history-more'));
    await waitFor(() =>
      expect(api.listarHistorico).toHaveBeenLastCalledWith(expect.objectContaining({ antesDe: 2 })),
    );
    expect(await screen.findByTestId('history-item-1')).toBeTruthy();
    expect(screen.getByTestId('history-item-3')).toBeTruthy();
    expect(screen.queryByTestId('history-more')).toBeNull();
  });

  it('auditoria: só ações e ferramentas, com integridade e detalhes', async () => {
    api.listarHistorico.mockResolvedValueOnce({ itens: [nota], mais: false }).mockResolvedValue({ itens: [ferramenta], mais: false });
    api.verificarIntegridade.mockResolvedValue({ ok: true, linhas: 42, quebra_em: null });
    render(<HistoryPage />);
    await screen.findByTestId('history-list');

    fireEvent.click(screen.getByTestId('history-tab-auditoria'));
    await waitFor(() =>
      expect(api.listarHistorico).toHaveBeenLastCalledWith(expect.objectContaining({ tipos: ['acao', 'ferramenta'] })),
    );
    expect(screen.queryByTestId('history-type-nota')).toBeNull();
    expect((await screen.findByTestId('history-integrity')).textContent).toContain('Registro íntegro (42 linhas)');

    const item = await screen.findByTestId('history-item-9');
    expect(item.textContent).toContain('Agente');
    expect(item.textContent).toContain('Assistido');
    expect(screen.getByTestId('history-result-9').textContent).toBe('Bloqueado');

    fireEvent.click(screen.getByTestId('history-expand-9'));
    const detalhe = screen.getByTestId('audit-detail');
    expect(detalhe.textContent).toContain('file_write');
    expect(detalhe.textContent).toContain('caminho');
    expect(detalhe.textContent).toContain('C:\\notas.txt');
    expect(detalhe.textContent).toContain('Moderado');
    expect(detalhe.textContent).toContain('Pedi "confirmo" antes de escrever.');
  });

  it('avisa quando o registro foi alterado', async () => {
    api.listarHistorico.mockResolvedValue({ itens: [ferramenta], mais: false });
    api.verificarIntegridade.mockResolvedValue({ ok: false, linhas: 42, quebra_em: 17 });
    render(<HistoryPage />);
    fireEvent.click(screen.getByTestId('history-tab-auditoria'));
    expect((await screen.findByTestId('history-integrity')).textContent).toContain(
      'Registro alterado a partir da atividade #17',
    );
  });

  it('vazio e erro', async () => {
    api.listarHistorico.mockResolvedValueOnce({ itens: [], mais: false });
    render(<HistoryPage />);
    expect((await screen.findByTestId('history-empty')).textContent).toContain('Nada no histórico ainda');
    cleanup();

    api.listarHistorico.mockRejectedValue(new Error('Reinicie o servidor do Nicx para usar o histórico e a autonomia.'));
    render(<HistoryPage />);
    expect((await screen.findByRole('alert')).textContent).toContain('Reinicie o servidor');
  });
});
