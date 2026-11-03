// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { PlanProgress } from '../lib/planejador';

const api = vi.hoisted(() => ({
  proporEtapas: vi.fn(),
  criarPlano: vi.fn(),
  obterProgresso: vi.fn(),
  reajustarPlano: vi.fn(),
  interpretarPrazo: vi.fn(),
}));
const projects = vi.hoisted(() => ({ listProjects: vi.fn() }));

vi.mock('../lib/planejador', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/planejador')>()),
  ...api,
}));
vi.mock('../lib/projetos-api', () => projects);

import { PlannerPage } from './PlannerPage';

function progress(over: Partial<PlanProgress>): PlanProgress {
  return {
    projeto: 'p1',
    nome: 'Aprender inglês',
    prazo: '2027-06-30',
    dias_restantes: 30,
    total: 4,
    feitas: 2,
    percentual: 50,
    minutos_total: 240,
    minutos_feitos: 120,
    atrasadas: [],
    proxima: { id: 't3', texto: 'Praticar conversação', prazo: '2027-05-10' },
    no_ritmo: true,
    ...over,
  };
}

const summary = (id: string, nome: string) => ({
  id,
  nome,
  estado: '',
  objetivo: '',
  ultima_atividade: '2026-11-01T10:00:00',
  pendencias_abertas: 2,
  arquivado: false,
});

const proposal = {
  prazo: '2027-06-30',
  etapas: [
    { texto: 'Revisar o básico', minutos: 60, depende_de: [] },
    { texto: 'Estudar vocabulário de viagem', minutos: 90, depende_de: [0] },
    { texto: 'Simular uma conversa', minutos: 45, depende_de: [0, 1] },
  ],
};

function renderPage() {
  return render(
    <MemoryRouter>
      <PlannerPage />
    </MemoryRouter>,
  );
}

async function fillAndPropose() {
  renderPage();
  fireEvent.change(screen.getByTestId('planner-goal'), { target: { value: 'Aprender inglês para viagens' } });
  fireEvent.change(screen.getByTestId('planner-deadline'), { target: { value: '2027-06-30' } });
  fireEvent.click(screen.getByTestId('planner-propose'));
}

// Os testes rodam com os textos em português (src/i18n/test-setup.ts).
describe('PlannerPage', () => {
  beforeEach(() => {
    projects.listProjects.mockResolvedValue({ projetos: [], atual: null });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('propõe as etapas e mostra a espera enquanto o modelo trabalha', async () => {
    let resolve: (value: typeof proposal) => void = () => {};
    api.proporEtapas.mockReturnValue(new Promise((r) => (resolve = r)));
    await fillAndPropose();

    expect(screen.getByTestId('planner-waiting').textContent).toContain('O modelo local está montando as etapas');
    expect(api.proporEtapas).toHaveBeenCalledWith(
      'Aprender inglês para viagens',
      '2027-06-30',
      'pt-BR',
      expect.any(AbortSignal),
    );
    resolve(proposal);

    const steps = await screen.findByTestId('planner-steps');
    expect(screen.queryByTestId('planner-waiting')).toBeNull();
    expect((screen.getByTestId('planner-step-text-1') as HTMLInputElement).value).toBe('Estudar vocabulário de viagem');
    expect(screen.getByTestId('planner-step-2').textContent).toContain('depois de #1, #2');
    expect(steps.textContent).toContain('3 etapas');
  });

  it('cancela a proposta', async () => {
    api.proporEtapas.mockImplementation(
      (_o: string, _p: string, _i: string, signal: AbortSignal) =>
        new Promise((_, reject) =>
          signal.addEventListener('abort', () => reject(new DOMException('cancelado', 'AbortError'))),
        ),
    );
    await fillAndPropose();
    fireEvent.click(screen.getByTestId('planner-cancel'));
    await waitFor(() => expect(screen.queryByTestId('planner-waiting')).toBeNull());
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.queryByTestId('planner-steps')).toBeNull();
  });

  it('mostra o erro do modelo local', async () => {
    api.proporEtapas.mockRejectedValue(new Error('Nenhum modelo local carregado. Ligue o Ollama e escolha um modelo.'));
    await fillAndPropose();
    expect((await screen.findByRole('alert')).textContent).toContain('Nenhum modelo local carregado');
  });

  it('cria o plano com as etapas editadas', async () => {
    api.proporEtapas.mockResolvedValue(proposal);
    api.criarPlano.mockResolvedValue({
      projeto: { id: 'p9', nome: 'Inglês', prazo: '2027-06-30' },
      progresso: progress({ projeto: 'p9', nome: 'Inglês', total: 2, feitas: 0, percentual: 0 }),
    });
    await fillAndPropose();
    await screen.findByTestId('planner-steps');

    // Tira a primeira: as dependências das outras andam junto.
    fireEvent.click(screen.getByTestId('planner-step-remove-0'));
    fireEvent.change(screen.getByTestId('planner-step-text-0'), { target: { value: 'Vocabulário de aeroporto' } });
    fireEvent.change(screen.getByTestId('planner-step-minutes-1'), { target: { value: '30' } });
    fireEvent.change(screen.getByTestId('planner-name'), { target: { value: 'Inglês' } });
    fireEvent.click(screen.getByTestId('planner-create'));

    await waitFor(() => expect(api.criarPlano).toHaveBeenCalledTimes(1));
    expect(api.criarPlano).toHaveBeenCalledWith({
      objetivo: 'Aprender inglês para viagens',
      prazo: '2027-06-30',
      etapas: [
        { texto: 'Vocabulário de aeroporto', minutos: 90, depende_de: [] },
        { texto: 'Simular uma conversa', minutos: 30, depende_de: [0] },
      ],
      nome: 'Inglês',
      idioma: 'pt-BR',
    });
    const created = await screen.findByTestId('planner-created');
    expect(created.textContent).toContain('Plano "Inglês" criado');
    expect(created.textContent).toContain('2 etapas');
    expect(screen.queryByTestId('planner-steps')).toBeNull();
    expect(projects.listProjects).toHaveBeenCalledTimes(2);
  });

  it('usa o prazo escrito em palavras', async () => {
    api.interpretarPrazo.mockResolvedValue('2027-12-31');
    renderPage();
    fireEvent.change(screen.getByTestId('planner-deadline-text'), { target: { value: 'até dezembro do ano que vem' } });
    fireEvent.click(screen.getByTestId('planner-deadline-resolve'));
    await waitFor(() => expect((screen.getByTestId('planner-deadline') as HTMLInputElement).value).toBe('2027-12-31'));
    expect(api.interpretarPrazo).toHaveBeenCalledWith('até dezembro do ano que vem');
  });

  it('mostra o progresso só dos projetos com prazo e reajusta', async () => {
    projects.listProjects.mockResolvedValue({
      projetos: [summary('p1', 'Aprender inglês'), summary('p2', 'Site')],
      atual: null,
    });
    api.obterProgresso.mockImplementation(async (id: string) =>
      id === 'p1'
        ? progress({
            no_ritmo: false,
            atrasadas: [{ id: 't1', texto: 'Revisar o básico', prazo: '2026-10-20' }],
          })
        : progress({ projeto: 'p2', nome: 'Site', prazo: '', dias_restantes: null }),
    );
    api.reajustarPlano.mockResolvedValue(progress({ atrasadas: [], no_ritmo: true, prazo: '2027-08-31' }));
    renderPage();

    const plan = await screen.findByTestId('plan-p1');
    expect(screen.queryByTestId('plan-p2')).toBeNull();
    expect(screen.getByTestId('plan-progress-p1').textContent).toBe('2 de 4 etapas · 50%');
    expect(plan.textContent).toContain('faltam 30 dias');
    expect(plan.textContent).toContain('Próxima: Praticar conversação');
    expect(screen.getByTestId('plan-pace-p1').textContent).toBe('Atrás do ritmo');
    expect(screen.getByTestId('plan-late-p1').textContent).toContain('Revisar o básico');
    expect(screen.getByRole('progressbar').getAttribute('aria-valuenow')).toBe('50');

    fireEvent.change(screen.getByTestId('plan-deadline-p1'), { target: { value: '2027-08-31' } });
    fireEvent.click(screen.getByTestId('plan-adjust-p1'));
    await waitFor(() => expect(api.reajustarPlano).toHaveBeenCalledWith('p1', '2027-08-31'));
    await waitFor(() => expect(screen.queryByTestId('plan-late-p1')).toBeNull());
    expect(screen.getByTestId('plan-pace-p1').textContent).toBe('No ritmo');
  });

  it('sem planos', async () => {
    renderPage();
    expect((await screen.findByTestId('plans-empty')).textContent).toContain('Nenhum plano com prazo ainda');
  });
});
