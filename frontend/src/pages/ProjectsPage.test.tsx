// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Project, ProjectList } from '../lib/projetos-api';

const api = vi.hoisted(() => ({
  listProjects: vi.fn(),
  getProject: vi.fn(),
  createProject: vi.fn(),
  updateProject: vi.fn(),
  deleteProject: vi.fn(),
  addDecision: vi.fn(),
  addTask: vi.fn(),
  setTaskDone: vi.fn(),
  deleteTask: vi.fn(),
  fetchProjectSignals: vi.fn(),
}));

vi.mock('../lib/projetos-api', () => api);

import { ProjectsPage } from './ProjectsPage';

const now = new Date().toISOString();

const lumen: Project = {
  id: 'p1',
  nome: 'Lumen',
  objetivo: 'Dados públicos',
  estado: 'API pronta, falta a tela de login',
  pastas: ['C:\\dev\\lumen'],
  arquivos: [],
  decisoes: [{ texto: 'Usar Postgres', data: now, origem: '' }],
  pendencias: [
    { id: 't1', texto: 'Comprar o domínio', feita: false, criada_em: now, feita_em: '', origem: '' },
    { id: 't2', texto: 'Revisar textos', feita: false, criada_em: now, feita_em: '', origem: 'auto' },
  ],
  proximos_passos: ['Tela de login'],
  criado_em: now,
  ultima_atividade: now,
  idioma: '',
  arquivado: false,
};

const list: ProjectList = {
  projetos: [
    {
      id: 'p1',
      nome: 'Lumen',
      estado: lumen.estado,
      objetivo: lumen.objetivo,
      ultima_atividade: now,
      pendencias_abertas: 2,
      arquivado: false,
    },
  ],
  atual: 'p1',
};

function ChatProbe() {
  const location = useLocation();
  const state = location.state as { nicxPrompt?: string } | null;
  return <div data-testid="chat-prompt">{state?.nicxPrompt}</div>;
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/projetos']}>
      <Routes>
        <Route path="/projetos" element={<ProjectsPage />} />
        <Route path="/" element={<ChatProbe />} />
      </Routes>
    </MemoryRouter>,
  );
}

// Os testes rodam com os textos em português (src/i18n/test-setup.ts).
describe('ProjectsPage', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('lista os projetos e abre o da janela em uso', async () => {
    api.listProjects.mockResolvedValue(list);
    api.getProject.mockResolvedValue(lumen);
    api.fetchProjectSignals.mockResolvedValue({
      git: { pasta: 'C:\\dev\\lumen', branch: 'main', commits: [{ hash: 'abc', data: now, assunto: 'API de dados' }], alterados: ['a.py'], total_alterados: 1 },
      recentes: [],
    });
    renderPage();

    const lista = await screen.findByTestId('projects-list');
    expect(lista.textContent).toContain('Lumen');
    expect(lista.textContent).toContain('Pendências abertas: 2');
    expect(lista.textContent).toContain('Aberto agora');

    const detalhe = await screen.findByTestId('project-detail');
    expect(api.getProject).toHaveBeenCalledWith('p1');
    expect((screen.getByTestId('project-state') as HTMLTextAreaElement).value).toBe(lumen.estado);
    expect(detalhe.textContent).toContain('Usar Postgres');
    expect(detalhe.textContent).toContain('sugerida');
    expect((await screen.findByTestId('project-git')).textContent).toContain('branch main');
  });

  it('marca pendência como feita e salva o estado', async () => {
    api.listProjects.mockResolvedValue(list);
    api.getProject.mockResolvedValue(lumen);
    api.fetchProjectSignals.mockResolvedValue({ git: null, recentes: [] });
    const feita = {
      ...lumen,
      pendencias: [{ ...lumen.pendencias[0], feita: true, feita_em: now }, lumen.pendencias[1]],
    };
    api.setTaskDone.mockResolvedValue(feita);
    api.updateProject.mockResolvedValue({ ...lumen, estado: 'Login pronto' });
    renderPage();

    fireEvent.click(await screen.findByLabelText('Marcar "Comprar o domínio" como feita'));
    await waitFor(() => expect(api.setTaskDone).toHaveBeenCalledWith('p1', 't1', true));
    expect(await screen.findByLabelText('Reabrir "Comprar o domínio"')).toBeTruthy();

    fireEvent.change(screen.getByTestId('project-state'), { target: { value: 'Login pronto' } });
    fireEvent.click(screen.getByTestId('project-save'));
    await waitFor(() =>
      expect(api.updateProject).toHaveBeenCalledWith('p1', {
        objetivo: 'Dados públicos',
        estado: 'Login pronto',
        proximos_passos: ['Tela de login'],
      }),
    );
  });

  it('adiciona pendência e decisão', async () => {
    api.listProjects.mockResolvedValue(list);
    api.getProject.mockResolvedValue(lumen);
    api.fetchProjectSignals.mockResolvedValue({ git: null, recentes: [] });
    api.addTask.mockResolvedValue(lumen);
    api.addDecision.mockResolvedValue(lumen);
    renderPage();

    const tarefa = await screen.findByTestId('project-add-task');
    fireEvent.change(tarefa, { target: { value: 'Testar no Mac' } });
    fireEvent.keyDown(tarefa, { key: 'Enter' });
    await waitFor(() => expect(api.addTask).toHaveBeenCalledWith('p1', 'Testar no Mac'));

    const decisao = screen.getByTestId('project-add-decision');
    fireEvent.change(decisao, { target: { value: 'Sem login social' } });
    fireEvent.keyDown(decisao, { key: 'Enter' });
    await waitFor(() => expect(api.addDecision).toHaveBeenCalledWith('p1', 'Sem login social'));
  });

  it('"Continuar de onde parei" manda o pedido ao chat', async () => {
    api.listProjects.mockResolvedValue(list);
    api.getProject.mockResolvedValue(lumen);
    api.fetchProjectSignals.mockResolvedValue({ git: null, recentes: [] });
    renderPage();

    fireEvent.click(await screen.findByTestId('project-continue'));
    expect((await screen.findByTestId('chat-prompt')).textContent).toBe(
      'Continue de onde parei no projeto Lumen',
    );
  });

  it('sem projetos mostra como começar e cria um', async () => {
    api.listProjects.mockResolvedValueOnce({ projetos: [], atual: null }).mockResolvedValue(list);
    api.createProject.mockResolvedValue(lumen);
    api.fetchProjectSignals.mockResolvedValue({ git: null, recentes: [] });
    renderPage();

    expect((await screen.findByTestId('projects-empty')).textContent).toContain('cria o projeto Nome');
    fireEvent.click(screen.getByTestId('project-new'));
    fireEvent.change(screen.getByTestId('project-name'), { target: { value: 'Lumen' } });
    fireEvent.click(screen.getByTestId('project-create'));
    await waitFor(() => expect(api.createProject).toHaveBeenCalledWith('Lumen', '', []));
    expect(await screen.findByTestId('project-detail')).toBeTruthy();
  });

  it('erro do servidor aparece', async () => {
    api.listProjects.mockRejectedValue(new Error('Reinicie o servidor do Nicx para usar os projetos.'));
    renderPage();
    expect((await screen.findByRole('alert')).textContent).toContain('Reinicie o servidor');
  });
});
