// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { PackPreview } from '../lib/extensoes';

const api = vi.hoisted(() => ({
  listarPacotes: vi.fn(),
  previaPacote: vi.fn(),
  instalarPacote: vi.fn(),
  desinstalarPacote: vi.fn(),
  exportarPacote: vi.fn(),
  baixarPacote: vi.fn(),
  listarMcp: vi.fn(),
  criarMcp: vi.fn(),
  atualizarMcp: vi.fn(),
  apagarMcp: vi.fn(),
  testarMcp: vi.fn(),
  recarregarMcp: vi.fn(),
  listarHabilidades: vi.fn(),
  criarHabilidade: vi.fn(),
  atualizarHabilidade: vi.fn(),
  ligarHabilidade: vi.fn(),
  apagarHabilidade: vi.fn(),
  importarHabilidadesZip: vi.fn(),
  instalarHabilidadesGithub: vi.fn(),
  recarregarHabilidades: vi.fn(),
  listarLoja: vi.fn(),
  previaLoja: vi.fn(),
  instalarDaLoja: vi.fn(),
}));

vi.mock('../lib/extensoes', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/extensoes')>()),
  ...api,
}));
vi.mock('../lib/assistentes', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/assistentes')>()),
  listarAssistentes: vi.fn().mockResolvedValue({ assistentes: [], ativo: null, prontos: [], ferramentas: [], limites: {} }),
}));
vi.mock('../lib/rotinas', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/rotinas')>()),
  listarRotinas: vi.fn().mockResolvedValue({ rotinas: [], modelos: [] }),
}));

import { ExtensionsPage } from './ExtensionsPage';

function preview(over: Partial<PackPreview> = {}): PackPreview {
  return {
    id: 'professor',
    nome: 'Professor',
    descricao: 'Aulas e correções.',
    versao: '1.0.0',
    autor: 'Falkyria',
    pronto: true,
    itens: { assistentes: ['Planejador de aulas'], rotinas: ['Hora de corrigir'], habilidades: ['Plano de aula'], mcp: [] },
    permissoes: { comandos: [], enderecos: [], segredos: [], ferramentas: [], todas_as_ferramentas: false, rotinas_com_horario: [] },
    problemas: [],
    instalado: false,
    versao_instalada: '',
    ...over,
  };
}

beforeEach(() => {
  for (const fn of Object.values(api)) fn.mockReset();
  api.listarPacotes.mockResolvedValue({ prontos: [preview()], instalados: [] });
  api.listarMcp.mockResolvedValue({
    servidores: [],
    catalogo: [{ chave: 'github', descricao: 'GitHub', args: ['-y', '@modelcontextprotocol/server-github'], env: ['GITHUB_PERSONAL_ACCESS_TOKEN'], pede_args: '', confianca: 'perguntar', comando: 'npx' }],
    npx: false,
  });
  api.listarHabilidades.mockResolvedValue({ habilidades: [], pasta: 'C:/skills' });
  api.recarregarMcp.mockResolvedValue(undefined);
  api.recarregarHabilidades.mockResolvedValue(undefined);
  api.listarLoja.mockResolvedValue([]);
});
afterEach(cleanup);

describe('ExtensionsPage: pacotes', () => {
  it('instala um pacote pronto', async () => {
    api.instalarPacote.mockResolvedValue({ instalado: { id: 'professor' }, pulados: [] });
    render(<ExtensionsPage />);
    fireEvent.click(screen.getByTestId('ext-tab-packs'));
    fireEvent.click(await screen.findByTestId('pack-install-professor'));
    await waitFor(() => expect(api.instalarPacote).toHaveBeenCalledWith(expect.objectContaining({ pronto: 'professor' })));
    expect(await screen.findByText('Pacote "Professor" instalado.')).toBeTruthy();
  });

  it('mostra o que o pacote importado faz e só leva MCP se marcar', async () => {
    const importado = preview({
      id: 'meu',
      nome: 'Meu pacote',
      pronto: false,
      itens: { assistentes: [], rotinas: [], habilidades: [], mcp: ['gh'] },
      permissoes: { comandos: ['npx -y servidor'], enderecos: [], segredos: ['TOKEN'], ferramentas: [], todas_as_ferramentas: true, rotinas_com_horario: [] },
    });
    api.previaPacote.mockResolvedValue(importado);
    api.instalarPacote.mockResolvedValue({ instalado: { id: 'meu' }, pulados: [] });
    render(<ExtensionsPage />);
    fireEvent.click(screen.getByTestId('ext-tab-packs'));
    const file = new File(['{"formato":1}'], 'meu.nicx.json', { type: 'application/json' });
    fireEvent.change(await screen.findByTestId('pack-file'), { target: { files: [file] } });
    const perms = await screen.findByTestId('pack-perms-meu');
    expect(perms.textContent).toContain('Roda programas no PC: npx -y servidor');
    expect(perms.textContent).toContain('Pede chaves ou senhas: TOKEN');
    expect(perms.textContent).toContain('todas as ferramentas');
    fireEvent.click(screen.getByTestId('pack-install-imported'));
    await waitFor(() => expect(api.instalarPacote).toHaveBeenCalledWith(expect.objectContaining({ com_mcp: false })));
  });
});

describe('ExtensionsPage: servidores MCP', () => {
  it('adiciona do catálogo, salva e liga no chat', async () => {
    api.criarMcp.mockResolvedValue({});
    render(<ExtensionsPage />);
    fireEvent.click(screen.getByTestId('ext-tab-mcp'));
    expect(await screen.findByTestId('mcp-no-npx')).toBeTruthy();
    fireEvent.click(screen.getByTestId('mcp-add-github'));
    expect((screen.getByTestId('mcp-name') as HTMLInputElement).value).toBe('github');
    expect((screen.getByTestId('mcp-env') as HTMLTextAreaElement).value).toBe('GITHUB_PERSONAL_ACCESS_TOKEN=');
    fireEvent.change(screen.getByTestId('mcp-env'), { target: { value: 'GITHUB_PERSONAL_ACCESS_TOKEN=abc' } });
    fireEvent.click(screen.getByTestId('mcp-save'));
    await waitFor(() => expect(api.criarMcp).toHaveBeenCalled());
    const enviado = api.criarMcp.mock.calls[0][0];
    expect(enviado.env).toEqual({ GITHUB_PERSONAL_ACCESS_TOKEN: 'abc' });
    expect(enviado.args).toEqual(['-y', '@modelcontextprotocol/server-github']);
    await waitFor(() => expect(api.recarregarMcp).toHaveBeenCalled());
  });

  it('testa e mostra as ferramentas achadas', async () => {
    api.testarMcp.mockResolvedValue({ ok: true, ferramentas: [{ nome: 'create_issue', descricao: '' }], erro: '' });
    render(<ExtensionsPage />);
    fireEvent.click(screen.getByTestId('ext-tab-mcp'));
    fireEvent.click(await screen.findByTestId('mcp-add-github'));
    fireEvent.click(screen.getByTestId('mcp-test'));
    expect((await screen.findByTestId('mcp-test-result')).textContent).toContain('create_issue');
  });
});

describe('ExtensionsPage: habilidades', () => {
  it('cria e liga no chat', async () => {
    api.criarHabilidade.mockResolvedValue({ nome: 'ata', titulo: 'Ata' });
    render(<ExtensionsPage />);
    fireEvent.click(screen.getByTestId('ext-tab-skills'));
    fireEvent.click(await screen.findByTestId('skill-new'));
    fireEvent.click(screen.getByTestId('skill-save'));
    expect(await screen.findByText('Preencha o título, quando usar e as instruções.')).toBeTruthy();
    fireEvent.change(screen.getByTestId('skill-title'), { target: { value: 'Ata' } });
    fireEvent.change(screen.getByTestId('skill-when'), { target: { value: 'Quando pedirem ata.' } });
    fireEvent.change(screen.getByTestId('skill-instructions'), { target: { value: 'Liste decisões.' } });
    fireEvent.click(screen.getByTestId('skill-save'));
    await waitFor(() => expect(api.criarHabilidade).toHaveBeenCalledWith({ titulo: 'Ata', descricao: 'Quando pedirem ata.', instrucoes: 'Liste decisões.' }));
    await waitFor(() => expect(api.recarregarHabilidades).toHaveBeenCalled());
  });

  it('habilidade perigosa só entra ao confirmar', async () => {
    api.importarHabilidadesZip
      .mockResolvedValueOnce([{ nome: 'limpa', ok: false, pede_confirmacao: true, perigosas: ['shell:execute'] }])
      .mockResolvedValueOnce([{ nome: 'limpa', ok: true }]);
    render(<ExtensionsPage />);
    fireEvent.click(screen.getByTestId('ext-tab-skills'));
    const file = new File(['zip'], 'h.zip', { type: 'application/zip' });
    fireEvent.change(await screen.findByTestId('skill-zip'), { target: { files: [file] } });
    fireEvent.click(await screen.findByTestId('skill-confirm-dangerous'));
    await waitFor(() => expect(api.importarHabilidadesZip).toHaveBeenLastCalledWith(file, true));
    expect(await screen.findByText('Importadas: limpa.')).toBeTruthy();
  });
});

describe('ExtensionsPage: loja', () => {
  const item = {
    id: 'saude',
    nome: 'Saúde',
    descricao: 'Para clínicas.',
    autor: 'Falkyria',
    categoria: 'saude',
    versao: '1.1.0',
    downloads: 12,
    atualizado_em: '',
    versao_instalada: '1.0.0',
    atualizacao: true,
  };

  it('mostra atualização, confere e instala com MCP marcado', async () => {
    api.listarLoja.mockResolvedValue([item, { ...item, id: 'outro', nome: 'Outro', categoria: 'educacao', atualizacao: false, versao_instalada: '' }]);
    api.previaLoja.mockResolvedValue(preview({ id: 'saude', nome: 'Saúde', pronto: false, itens: { assistentes: ['Recepção'], rotinas: [], habilidades: [], mcp: ['agenda'] } }));
    api.instalarDaLoja.mockResolvedValue({ instalado: { id: 'saude' }, pulados: [] });
    render(<ExtensionsPage />);
    expect((await screen.findByTestId('store-saude')).textContent).toContain('Atualização');
    fireEvent.click(screen.getByTestId('store-category-educacao'));
    expect(screen.queryByTestId('store-saude')).toBeNull();
    fireEvent.click(screen.getByTestId('store-category-all'));
    fireEvent.click(screen.getByTestId('store-open-saude'));
    expect((await screen.findByTestId('store-preview')).textContent).toContain('Assinatura da Falkyria conferida.');
    fireEvent.click(screen.getByTestId('store-with-mcp'));
    fireEvent.click(screen.getByTestId('store-install'));
    await waitFor(() => expect(api.instalarDaLoja).toHaveBeenCalledWith('saude', true));
    expect(await screen.findByText('Pacote "Saúde" instalado.')).toBeTruthy();
  });

  it('avisa quando a loja não responde', async () => {
    api.listarLoja.mockRejectedValue(new Error('A loja não respondeu: sem conexão com a loja'));
    render(<ExtensionsPage />);
    expect(await screen.findByText('A loja não respondeu: sem conexão com a loja')).toBeTruthy();
  });
});
