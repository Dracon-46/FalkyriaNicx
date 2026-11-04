// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Assistant, AssistantList } from '../lib/assistentes';

const api = vi.hoisted(() => ({
  listarAssistentes: vi.fn(),
  criarAssistente: vi.fn(),
  atualizarAssistente: vi.fn(),
  apagarAssistente: vi.fn(),
  ativarAssistente: vi.fn(),
  proporAssistente: vi.fn(),
}));

vi.mock('../lib/assistentes', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/assistentes')>()),
  ...api,
}));

import { AssistantsPage } from './AssistantsPage';
import { AssistantPicker } from '../components/Chat/AssistantPicker';

function assistant(over: Partial<Assistant> = {}): Assistant {
  return {
    id: 'a1',
    nome: 'Tutor de estudos',
    instrucoes: 'Explique passo a passo.',
    descricao: 'Explica a matéria.',
    ferramentas: [],
    memoria: true,
    saudacao: 'Qual matéria hoje?',
    modelo: '',
    criado_em: '2026-11-03T10:00:00',
    atualizado_em: '2026-11-03T10:00:00',
    ...over,
  };
}

function list(over: Partial<AssistantList> = {}): AssistantList {
  return {
    assistentes: [],
    ativo: null,
    prontos: [
      assistant({ id: 'modelo-revisor', nome: 'Revisor de textos', modelo: 'revisor', memoria: false }),
      assistant({ id: 'modelo-pesquisa', nome: 'Pesquisador', modelo: 'pesquisa', ferramentas: ['web_search'] }),
    ],
    ferramentas: [
      { nome: 'web_search', descricao: 'Pesquisa na internet' },
      { nome: 'shell_exec', descricao: 'Roda comandos' },
    ],
    limites: { nome: 40, descricao: 200, instrucoes: 2000, saudacao: 200 },
    ...over,
  };
}

beforeEach(() => {
  for (const fn of Object.values(api)) fn.mockReset();
});
afterEach(cleanup);

describe('AssistantsPage', () => {
  it('mostra que quem fala é o Nicx e os modelos prontos', async () => {
    api.listarAssistentes.mockResolvedValue(list());
    render(<AssistantsPage />);
    expect(await screen.findByText('Agora quem fala é o Nicx de sempre.')).toBeTruthy();
    expect(screen.getByTestId('assistant-empty')).toBeTruthy();
    expect(screen.getByTestId('template-revisor').textContent).toContain('Sem ferramentas');
    expect(screen.getByTestId('template-pesquisa').textContent).toContain('Ferramentas: 1');
  });

  it('cria a partir de um modelo pronto, sem o id do modelo', async () => {
    api.listarAssistentes.mockResolvedValue(list());
    api.criarAssistente.mockResolvedValue(assistant({ id: 'novo', nome: 'Revisor de textos' }));
    render(<AssistantsPage />);
    fireEvent.click(await screen.findByTestId('template-use-revisor'));
    expect((screen.getByTestId('assistant-name') as HTMLInputElement).value).toBe('Revisor de textos');
    expect((screen.getByTestId('assistant-memory') as HTMLInputElement).checked).toBe(false);
    fireEvent.click(screen.getByTestId('assistant-save'));
    await waitFor(() => expect(api.criarAssistente).toHaveBeenCalledTimes(1));
    const enviado = api.criarAssistente.mock.calls[0][0];
    expect(enviado).not.toHaveProperty('id');
    expect(enviado).toMatchObject({ nome: 'Revisor de textos', modelo: 'revisor', memoria: false });
    expect(await screen.findByText('Assistente "Revisor de textos" salvo.')).toBeTruthy();
  });

  it('escolhe ferramentas e avisa de instruções longas', async () => {
    api.listarAssistentes.mockResolvedValue(list());
    api.criarAssistente.mockResolvedValue(assistant());
    render(<AssistantsPage />);
    fireEvent.click(await screen.findByTestId('assistant-new'));
    fireEvent.change(screen.getByTestId('assistant-name'), { target: { value: 'Pesquisa' } });
    fireEvent.change(screen.getByTestId('assistant-instructions'), { target: { value: 'x'.repeat(900) } });
    expect(screen.getByText('Instruções longas deixam cada resposta mais lenta neste PC.')).toBeTruthy();
    fireEvent.click(screen.getByTestId('assistant-tools-some'));
    fireEvent.click(screen.getByTestId('assistant-tool-web_search'));
    fireEvent.click(screen.getByTestId('assistant-save'));
    await waitFor(() => expect(api.criarAssistente).toHaveBeenCalled());
    expect(api.criarAssistente.mock.calls[0][0].ferramentas).toEqual(['web_search']);
  });

  it('não salva sem nome', async () => {
    api.listarAssistentes.mockResolvedValue(list());
    render(<AssistantsPage />);
    fireEvent.click(await screen.findByTestId('assistant-new'));
    fireEvent.click(screen.getByTestId('assistant-save'));
    expect(await screen.findByText('Dê um nome ao assistente.')).toBeTruthy();
    expect(api.criarAssistente).not.toHaveBeenCalled();
  });

  it('monta pela descrição e abre o rascunho para revisar', async () => {
    api.listarAssistentes.mockResolvedValue(list());
    api.proporAssistente.mockResolvedValue({
      nome: 'Revisor de contratos',
      instrucoes: 'Liste as cláusulas de risco.',
      descricao: 'Lê contratos.',
      ferramentas: [],
      memoria: true,
      saudacao: '',
      modelo: '',
    });
    render(<AssistantsPage />);
    fireEvent.change(await screen.findByTestId('assistant-describe'), { target: { value: 'revisa contratos de aluguel' } });
    fireEvent.click(screen.getByTestId('assistant-propose'));
    await waitFor(() =>
      expect((screen.getByTestId('assistant-name') as HTMLInputElement).value).toBe('Revisor de contratos'),
    );
    expect(api.proporAssistente.mock.calls[0][0]).toBe('revisa contratos de aluguel');
    expect(api.criarAssistente).not.toHaveBeenCalled();
  });

  it('usa, volta para o Nicx e apaga com confirmação', async () => {
    api.listarAssistentes.mockResolvedValue(list({ assistentes: [assistant()] }));
    api.ativarAssistente.mockImplementation(async (id: string | null) => id);
    api.apagarAssistente.mockResolvedValue(undefined);
    render(<AssistantsPage />);
    fireEvent.click(await screen.findByTestId('assistant-use-a1'));
    expect(await screen.findByText('Agora quem fala é o assistente "Tutor de estudos".')).toBeTruthy();
    expect(api.ativarAssistente).toHaveBeenLastCalledWith('a1');
    fireEvent.click(screen.getByTestId('assistant-back'));
    expect(await screen.findByText('Agora quem fala é o Nicx de sempre.')).toBeTruthy();
    expect(api.ativarAssistente).toHaveBeenLastCalledWith(null);
    fireEvent.click(screen.getByTestId('assistant-delete-a1'));
    expect(api.apagarAssistente).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('assistant-delete-a1'));
    await waitFor(() => expect(api.apagarAssistente).toHaveBeenCalledWith('a1'));
  });
});

describe('AssistantPicker', () => {
  it('some sem assistentes', async () => {
    api.listarAssistentes.mockResolvedValue(list());
    const { container } = render(<AssistantPicker refreshKey={0} />);
    await waitFor(() => expect(api.listarAssistentes).toHaveBeenCalled());
    expect(container.querySelector('select')).toBeNull();
  });

  it('troca de assistente e recarrega quando a resposta termina', async () => {
    api.listarAssistentes.mockResolvedValue(list({ assistentes: [assistant()], ativo: null }));
    api.ativarAssistente.mockImplementation(async (id: string | null) => id);
    const { rerender } = render(<AssistantPicker refreshKey={0} />);
    const select = (await screen.findByTestId('assistant-picker')) as HTMLSelectElement;
    expect(select.value).toBe('');
    fireEvent.change(select, { target: { value: 'a1' } });
    await waitFor(() => expect(api.ativarAssistente).toHaveBeenCalledWith('a1'));
    api.listarAssistentes.mockResolvedValue(list({ assistentes: [assistant()], ativo: null }));
    rerender(<AssistantPicker refreshKey={1} />);
    await waitFor(() => expect(api.listarAssistentes).toHaveBeenCalledTimes(2));
    await waitFor(() => expect((screen.getByTestId('assistant-picker') as HTMLSelectElement).value).toBe(''));
  });
});
