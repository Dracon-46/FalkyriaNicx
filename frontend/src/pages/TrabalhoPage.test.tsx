// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Task } from '../lib/trabalho';

const api = vi.hoisted(() => ({
  escolherPasta: vi.fn(),
  listarTarefas: vi.fn(),
  verTarefa: vi.fn(),
  criarTarefa: vi.fn(),
  aprovarTarefa: vi.fn(),
  acaoTarefa: vi.fn(),
  responderTarefa: vi.fn(),
}));

vi.mock('../lib/trabalho', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/trabalho')>()),
  ...api,
}));

import { TrabalhoPage } from './TrabalhoPage';

function task(over: Partial<Task>): Task {
  return {
    id: 'abc',
    pasta: 'C:\\Docs\\Notas',
    pedido: 'junta as notas numa planilha',
    estado: 'aguardando_aprovacao',
    plano: [
      { descricao: 'ler as notas', estado: 'pendente', resultado: '' },
      { descricao: 'criar a planilha', estado: 'pendente', resultado: '' },
    ],
    registro: [],
    pergunta: null,
    resumo: '',
    erro: '',
    criado_em: '2026-11-19T10:00:00',
    atualizado_em: '2026-11-19T10:00:00',
    arquivos_mudados: [],
    ...over,
  };
}

describe('TrabalhoPage', () => {
  beforeEach(() => {
    Object.values(api).forEach((fn) => fn.mockReset());
    api.listarTarefas.mockResolvedValue([]);
  });
  afterEach(cleanup);

  it('monta o plano, deixa editar e aprova com os passos editados', async () => {
    api.criarTarefa.mockResolvedValue(task({}));
    api.aprovarTarefa.mockResolvedValue(task({ estado: 'executando' }));
    render(
      <MemoryRouter>
        <TrabalhoPage />
      </MemoryRouter>,
    );

    const create = screen.getByTestId('work-create');
    expect(create).toHaveProperty('disabled', true);
    fireEvent.change(screen.getByTestId('work-folder'), { target: { value: 'C:\\Docs\\Notas' } });
    fireEvent.change(screen.getByTestId('work-request'), { target: { value: 'junta as notas numa planilha' } });
    fireEvent.click(create);
    await waitFor(() => expect(api.criarTarefa).toHaveBeenCalledWith('C:\\Docs\\Notas', 'junta as notas numa planilha'));

    const step = await screen.findByTestId('work-step-1');
    fireEvent.change(step, { target: { value: 'criar planilha.xlsx' } });
    fireEvent.click(screen.getByTestId('work-approve'));
    await waitFor(() => expect(api.aprovarTarefa).toHaveBeenCalledWith('abc', ['ler as notas', 'criar planilha.xlsx']));
  });

  it('pergunta antes de apagar e manda a resposta', async () => {
    const waiting = task({ estado: 'aguardando_confirmacao', pergunta: { texto: "Apagar 'velho.txt'?" } });
    api.listarTarefas.mockResolvedValue([waiting]);
    api.verTarefa.mockResolvedValue(waiting);
    api.responderTarefa.mockResolvedValue(task({ estado: 'executando' }));
    render(
      <MemoryRouter>
        <TrabalhoPage />
      </MemoryRouter>,
    );

    expect((await screen.findByTestId('work-question')).textContent).toContain('velho.txt');
    fireEvent.click(screen.getByTestId('work-confirm-no'));
    await waitFor(() => expect(api.responderTarefa).toHaveBeenCalledWith('abc', false));
  });

  it('desfaz uma tarefa concluída', async () => {
    const done = task({
      estado: 'concluida',
      resumo: 'Criei notas.xlsx.',
      plano: [{ descricao: 'criar', estado: 'feito', resultado: 'ok' }],
      arquivos_mudados: ['notas.xlsx'],
    });
    api.listarTarefas.mockResolvedValue([done]);
    api.verTarefa.mockResolvedValue(done);
    api.acaoTarefa.mockResolvedValue({ ...done, estado: 'desfeita', arquivos_mudados: [] });
    render(
      <MemoryRouter>
        <TrabalhoPage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByText(done.pedido));
    expect((await screen.findByTestId('work-summary')).textContent).toBe('Criei notas.xlsx.');
    fireEvent.click(screen.getByTestId('work-undo'));
    await waitFor(() => expect(api.acaoTarefa).toHaveBeenCalledWith('abc', 'desfazer'));
  });
});
