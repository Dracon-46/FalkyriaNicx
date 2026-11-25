// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Inbox, InboxItem } from '../lib/caixa';

const api = vi.hoisted(() => ({ approveAction: vi.fn(), denyAction: vi.fn() }));
const trabalho = vi.hoisted(() => ({ responderTarefa: vi.fn() }));
const caixaApi = vi.hoisted(() => ({ obterCaixa: vi.fn(), dispensarAvisos: vi.fn() }));

vi.mock('../lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/api')>()),
  ...api,
}));
vi.mock('../lib/trabalho', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/trabalho')>()),
  ...trabalho,
}));
vi.mock('../lib/caixa', async (importOriginal) => {
  const real = await importOriginal<typeof import('../lib/caixa')>();
  return { ...real, ...caixaApi };
});

import { useCaixa } from '../lib/caixa';
import { InboxBell } from './InboxBell';

function item(over: Partial<InboxItem>): InboxItem {
  return {
    id: 'x',
    tipo: 'aprovacao',
    categoria: 'decisao',
    quando: new Date().toISOString(),
    titulo: '',
    texto: '',
    ref: 'r1',
    link: '',
    extra: {},
    ...over,
  };
}

const CAIXA: Inbox = {
  decisoes: [
    item({ id: 'aprovacao:a1', titulo: 'enviar_email', texto: 'Enviar o relatório', ref: 'a1', extra: { tier: 'high' } }),
    item({ id: 'trabalho:t1:pergunta', tipo: 'trabalho_pergunta', titulo: 'limpa a pasta', texto: 'Apagar velho.txt?', ref: 't1', link: '/trabalho' }),
  ],
  avisos: [
    item({ id: 'trabalho:t2:concluida', tipo: 'trabalho_concluida', categoria: 'aviso', titulo: 'faz a planilha', texto: 'Criei gastos.xlsx.', ref: 't2', link: '/trabalho' }),
  ],
  atividade: { trabalhando: true, esperando: 2, ultimo_concluido: '', ultimo_erro: '' },
};

function Where() {
  const loc = useLocation();
  return <div data-testid="where">{`${loc.pathname}|${(loc.state as { tarefa?: string } | null)?.tarefa ?? ''}`}</div>;
}

function renderBell() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <InboxBell />
      <Routes>
        <Route path="*" element={<Where />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('InboxBell', () => {
  beforeEach(() => {
    [...Object.values(api), ...Object.values(trabalho), ...Object.values(caixaApi)].forEach((fn) => fn.mockReset());
    caixaApi.obterCaixa.mockResolvedValue(CAIXA);
    caixaApi.dispensarAvisos.mockResolvedValue(undefined);
    useCaixa.setState({ caixa: structuredClone(CAIXA) });
  });
  afterEach(cleanup);

  it('mostra quantas decisões esperam e separa decisões de avisos', async () => {
    renderBell();
    expect(screen.getByTestId('inbox-count').textContent).toBe('2');
    fireEvent.click(screen.getByTestId('inbox-bell'));
    expect(await screen.findByTestId('inbox-decisions')).toBeTruthy();
    expect(screen.getByTestId('inbox-notices').textContent).toContain('Criei gastos.xlsx.');
  });

  it('responde a pergunta do modo Trabalho e aprova a ação do agente', async () => {
    trabalho.responderTarefa.mockResolvedValue({});
    api.approveAction.mockResolvedValue(undefined);
    caixaApi.obterCaixa.mockResolvedValue({ ...CAIXA, decisoes: [] });
    renderBell();
    fireEvent.click(screen.getByTestId('inbox-bell'));
    fireEvent.click(await screen.findByTestId('inbox-yes'));
    await waitFor(() => expect(trabalho.responderTarefa).toHaveBeenCalledWith('t1', true));
    fireEvent.click(screen.getByTestId('inbox-approve'));
    await waitFor(() => expect(api.approveAction).toHaveBeenCalledWith('a1'));
  });

  it('abre a tarefa concluída na página Trabalho e dispensa o aviso', async () => {
    renderBell();
    fireEvent.click(screen.getByTestId('inbox-bell'));
    fireEvent.click(await screen.findByTestId('inbox-open'));
    expect(screen.getByTestId('where').textContent).toBe('/trabalho|t2');
    expect(caixaApi.dispensarAvisos).toHaveBeenCalledWith(['trabalho:t2:concluida']);
  });

  it('limpa os avisos', async () => {
    caixaApi.obterCaixa.mockResolvedValue({ ...CAIXA, avisos: [] });
    renderBell();
    fireEvent.click(screen.getByTestId('inbox-bell'));
    fireEvent.click(await screen.findByTestId('inbox-clear'));
    await waitFor(() => expect(caixaApi.dispensarAvisos).toHaveBeenCalledWith('todos'));
    expect(screen.queryByTestId('inbox-notices')).toBeNull();
  });
});
