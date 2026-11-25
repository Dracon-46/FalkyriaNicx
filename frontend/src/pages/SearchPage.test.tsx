// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Conversation } from '../types';

const api = vi.hoisted(() => ({ buscarNoServidor: vi.fn() }));
vi.mock('../lib/busca', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/busca')>()),
  ...api,
}));

import { buscarConversas, palavras } from '../lib/busca';
import { useAppStore } from '../lib/store';
import { SearchPage } from './SearchPage';

function conversa(id: string, title: string, conteudo: string): Conversation {
  return {
    id,
    title,
    createdAt: 1,
    updatedAt: Date.parse('2026-11-20T10:00:00Z'),
    model: 'm',
    messages: [{ id: `${id}-m`, role: 'user', content: conteudo, timestamp: 1 } as Conversation['messages'][number]],
  };
}

describe('busca local', () => {
  it('sem acento, todas as palavras, título vale mais', () => {
    expect(palavras('Orçamento, PISO!')).toEqual(['orcamento', 'piso']);
    const lista = [
      conversa('a', 'Receita de bolo', 'quanto custa o piso de madeira?'),
      conversa('b', 'Piso da cozinha', 'orçamento do piso'),
      conversa('c', 'Outra', 'nada a ver'),
    ];
    expect(buscarConversas(lista, 'piso').map((h) => h.ref)).toEqual(['b', 'a']);
    expect(buscarConversas(lista, 'orcamento piso').map((h) => h.ref)).toEqual(['b']);
    expect(buscarConversas(lista, 'x')).toEqual([]);
  });
});

describe('SearchPage', () => {
  beforeEach(() => {
    api.buscarNoServidor.mockReset();
    useAppStore.setState({ conversations: [conversa('a', 'Piso da cozinha', 'orçamento do piso')] });
  });
  afterEach(cleanup);

  it('junta conversas e o que vem do servidor, agrupado por fonte', async () => {
    api.buscarNoServidor.mockResolvedValue({
      resultados: [
        { fonte: 'projeto', titulo: 'Reforma', trecho: 'trocar o piso', quando: '', link: '/projetos', ref: 'p1', pontos: 1, extra: {} },
        { fonte: 'nota', titulo: 'piso: ligar pro João', trecho: '', quando: '', link: '', ref: '0', pontos: 1, extra: {} },
      ],
      falharam: ['memoria'],
    });
    render(
      <MemoryRouter>
        <SearchPage />
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByTestId('search-input'), { target: { value: 'piso' } });
    expect(await screen.findByTestId('search-group-conversa')).toBeTruthy();
    await waitFor(() => expect(screen.getByTestId('search-group-projeto')).toBeTruthy());
    expect(screen.getByTestId('search-group-nota').textContent).toContain('ligar pro João');
    expect(api.buscarNoServidor).toHaveBeenCalledWith('piso', expect.anything());
    expect(document.body.textContent).toContain('Memória');
  });
});
