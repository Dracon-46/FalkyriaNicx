// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Routine, RoutineOptions } from '../lib/rotinas';

const api = vi.hoisted(() => ({
  listarRotinas: vi.fn(),
  opcoesRotinas: vi.fn(),
  criarRotina: vi.fn(),
  atualizarRotina: vi.fn(),
  apagarRotina: vi.fn(),
  executarRotina: vi.fn(),
  interpretarRotina: vi.fn(),
}));

vi.mock('../lib/rotinas', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/rotinas')>()),
  ...api,
}));

import { RoutinesPage } from './RoutinesPage';

function routine(over: Partial<Routine>): Routine {
  return {
    id: 'r1',
    nome: 'Trabalho',
    passos: [
      { kind: 'open', op: '', value: null, target: 'chrome', site: '', minutos: null },
      { kind: 'volume', op: 'set', value: 30, target: '', site: '', minutos: null },
    ],
    frases: ['hora de trabalhar'],
    agenda: { dias: ['seg', 'qua'], hora: '09:00' },
    ativa: true,
    criada_em: '2026-11-01T10:00:00',
    ultima_execucao: '',
    ultimo_agendado: '',
    idioma: 'pt-BR',
    ...over,
  };
}

const trabalho = routine({});
const foco = routine({
  id: 'modelo-foco',
  nome: 'Modo foco',
  passos: [
    { kind: 'close', op: '', value: null, target: 'whatsapp', site: '', minutos: null },
    { kind: 'volume', op: 'set', value: 25, target: '', site: '', minutos: null },
    { kind: 'remind', op: '', value: null, target: 'Fim do foco', site: '', minutos: 50 },
  ],
  frases: [],
  agenda: null,
});

const options: RoutineOptions = {
  tipos: ['open', 'volume', 'remind', 'close', 'lock'],
  apps: [
    { chave: 'chrome', rotulo: 'Chrome' },
    { chave: 'vs code', rotulo: 'VS Code' },
  ],
  fechar: [
    { chave: 'whatsapp', rotulo: 'o WhatsApp' },
    { chave: 'chrome', rotulo: 'o Chrome' },
    { chave: 'google chrome', rotulo: 'o Chrome' },
  ],
  pastas: ['downloads', 'area de trabalho'],
};

async function openEditor() {
  render(<RoutinesPage />);
  await screen.findByTestId('routines-list');
  // As listas do /opcoes chegaram: o passo "abrir" vira um select.
  await waitFor(() => expect(api.opcoesRotinas).toHaveBeenCalled());
  fireEvent.click(screen.getByTestId('routine-new'));
  return screen.getByTestId('routine-editor');
}

// Os testes rodam com os textos em português (src/i18n/test-setup.ts).
describe('RoutinesPage', () => {
  beforeEach(() => {
    api.listarRotinas.mockResolvedValue({ rotinas: [trabalho], modelos: [foco] });
    api.opcoesRotinas.mockResolvedValue(options);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it('lista as rotinas e os modelos', async () => {
    render(<RoutinesPage />);
    const card = await screen.findByTestId('routine-card-r1');
    expect(card.textContent).toContain('Trabalho');
    expect(card.textContent).toContain('Seg, Qua · 09:00');
    expect(card.textContent).toContain('Nunca rodou');
    expect(card.textContent).toContain('hora de trabalhar');
    await waitFor(() => expect(card.textContent).toContain('Abrir Chrome'));
    expect(card.textContent).toContain('Volume em 30%');
    expect(api.listarRotinas).toHaveBeenCalledWith('pt-BR');

    const modelo = screen.getByTestId('template-card-modelo-foco');
    expect(modelo.textContent).toContain('Modo foco');
    expect(modelo.textContent).toContain('Sem horário');
    expect(modelo.textContent).toContain('Fechar o WhatsApp');
    expect(modelo.textContent).toContain('Lembrete em 50 min: Fim do foco');
  });

  it('roda agora e mostra a mensagem', async () => {
    api.executarRotina.mockResolvedValue({ ok: true, mensagem: 'Pronto: abri o Chrome e pus o volume em 30.' });
    render(<RoutinesPage />);
    fireEvent.click(await screen.findByTestId('routine-run-r1'));
    await waitFor(() => expect(api.executarRotina).toHaveBeenCalledWith('r1', 'pt-BR'));
    expect((await screen.findByTestId('routine-notice')).textContent).toContain('Pronto: abri o Chrome');

    fireEvent.click(screen.getByTestId('template-run-modelo-foco'));
    await waitFor(() => expect(api.executarRotina).toHaveBeenCalledWith('modelo-foco', 'pt-BR'));
  });

  it('o editor monta os passos e salva com POST', async () => {
    const saved = routine({ id: 'r2', nome: 'Estudo' });
    api.criarRotina.mockResolvedValue(saved);
    await openEditor();

    fireEvent.change(screen.getByTestId('routine-name'), { target: { value: ' Estudo ' } });
    fireEvent.change(screen.getByTestId('routine-phrase-input'), { target: { value: 'bora estudar' } });
    fireEvent.click(screen.getByTestId('routine-phrase-add'));

    fireEvent.click(screen.getByTestId('routine-add-step'));
    await waitFor(() => expect(screen.getByTestId('routine-step-target-0').tagName).toBe('SELECT'));
    fireEvent.change(screen.getByTestId('routine-step-target-0'), { target: { value: 'vs code' } });

    fireEvent.click(screen.getByTestId('routine-add-step'));
    fireEvent.change(screen.getByTestId('routine-step-kind-1'), { target: { value: 'volume' } });
    fireEvent.change(screen.getByTestId('routine-step-value-1'), { target: { value: '30' } });

    fireEvent.click(screen.getByTestId('routine-add-step'));
    fireEvent.change(screen.getByTestId('routine-step-kind-2'), { target: { value: 'remind' } });
    fireEvent.change(screen.getByTestId('routine-step-minutos-2'), { target: { value: '50' } });

    // Troca a ordem: o volume vem primeiro.
    fireEvent.click(screen.getByTestId('routine-step-up-1'));

    fireEvent.click(screen.getByTestId('routine-schedule-toggle'));
    fireEvent.click(screen.getByTestId('routine-day-qua'));
    fireEvent.click(screen.getByTestId('routine-day-seg'));
    fireEvent.change(screen.getByTestId('routine-time'), { target: { value: '09:30' } });

    fireEvent.click(screen.getByTestId('routine-save'));
    await waitFor(() => expect(api.criarRotina).toHaveBeenCalledTimes(1));
    expect(api.criarRotina).toHaveBeenCalledWith({
      nome: 'Estudo',
      passos: [
        { kind: 'volume', op: 'set', value: 30, target: '', site: '', minutos: null },
        { kind: 'open', op: '', value: null, target: 'vs code', site: '', minutos: null },
        { kind: 'remind', op: '', value: null, target: 'o tempo acabou', site: '', minutos: 50 },
      ],
      frases: ['bora estudar'],
      agenda: { dias: ['seg', 'qua'], hora: '09:30' },
      ativa: true,
      idioma: 'pt-BR',
    });
    expect((await screen.findByTestId('routine-notice')).textContent).toContain('Rotina "Estudo" salva.');
    expect(screen.queryByTestId('routine-editor')).toBeNull();
    expect(api.listarRotinas).toHaveBeenCalledTimes(2);
  });

  it('não salva passo incompleto', async () => {
    await openEditor();
    fireEvent.change(screen.getByTestId('routine-name'), { target: { value: 'Teste' } });
    fireEvent.click(screen.getByTestId('routine-add-step'));
    fireEvent.click(screen.getByTestId('routine-save'));
    expect((await screen.findByRole('alert')).textContent).toContain('Complete o passo 1.');
    expect(api.criarRotina).not.toHaveBeenCalled();
  });

  it('descrever com palavras acrescenta os passos e o horário', async () => {
    api.interpretarRotina.mockResolvedValue({
      passos: [
        { kind: 'open', op: '', value: null, target: 'chrome', site: '', minutos: null },
        { kind: 'remind', op: '', value: null, target: 'o tempo acabou', site: '', minutos: 50 },
      ],
      agenda: { dias: ['seg'], hora: '09:00' },
      nao_entendi: ['dança'],
      proibidos: ['desliga o pc'],
    });
    await openEditor();
    fireEvent.click(screen.getByTestId('routine-add-step'));

    fireEvent.change(screen.getByTestId('routine-describe'), {
      target: { value: 'abre o chrome, timer de 50 minutos, dança, desliga o pc, toda segunda às 9h' },
    });
    fireEvent.click(screen.getByTestId('routine-interpret'));
    await waitFor(() =>
      expect(api.interpretarRotina).toHaveBeenCalledWith(
        'abre o chrome, timer de 50 minutos, dança, desliga o pc, toda segunda às 9h',
        'pt-BR',
      ),
    );
    await screen.findByTestId('routine-step-2');
    expect((screen.getByTestId('routine-step-target-1') as HTMLSelectElement).value).toBe('chrome');
    expect((screen.getByTestId('routine-step-minutos-2') as HTMLInputElement).value).toBe('50');
    expect((screen.getByTestId('routine-schedule-toggle') as HTMLInputElement).checked).toBe(true);
    expect(screen.getByTestId('routine-day-seg').getAttribute('aria-pressed')).toBe('true');
    expect((screen.getByTestId('routine-time') as HTMLInputElement).value).toBe('09:00');
    const avisos = screen.getByTestId('routine-warnings');
    expect(avisos.textContent).toContain('Não entendi: dança');
    expect(avisos.textContent).toContain('Não pode entrar numa rotina: desliga o pc');
  });

  it('usa o modelo e cria uma rotina nova', async () => {
    api.criarRotina.mockResolvedValue(routine({ id: 'r3', nome: 'Modo foco' }));
    render(<RoutinesPage />);
    fireEvent.click(await screen.findByTestId('template-use-modelo-foco'));
    expect((screen.getByTestId('routine-name') as HTMLInputElement).value).toBe('Modo foco');
    expect(screen.getByTestId('routine-step-2')).toBeTruthy();
    fireEvent.click(screen.getByTestId('routine-save'));
    await waitFor(() => expect(api.criarRotina).toHaveBeenCalledTimes(1));
    expect(api.criarRotina.mock.calls[0][0].passos).toHaveLength(3);
    expect(api.atualizarRotina).not.toHaveBeenCalled();
  });

  it('edita, liga/desliga e apaga com confirmação', async () => {
    api.atualizarRotina.mockImplementation(async (id: string, body: { ativa: boolean }) => routine({ id, ativa: body.ativa }));
    api.apagarRotina.mockResolvedValue(undefined);
    vi.stubGlobal('confirm', vi.fn(() => true));
    render(<RoutinesPage />);

    fireEvent.click(await screen.findByTestId('routine-toggle-r1'));
    await waitFor(() => expect(api.atualizarRotina).toHaveBeenCalledWith('r1', expect.objectContaining({ ativa: false })));
    await waitFor(() => expect((screen.getByTestId('routine-toggle-r1') as HTMLInputElement).checked).toBe(false));

    fireEvent.click(screen.getByTestId('routine-edit-r1'));
    expect((screen.getByTestId('routine-name') as HTMLInputElement).value).toBe('Trabalho');
    fireEvent.click(screen.getByTestId('routine-save'));
    await waitFor(() => expect(api.atualizarRotina).toHaveBeenCalledTimes(2));
    expect(api.atualizarRotina.mock.calls[1][0]).toBe('r1');

    fireEvent.click(await screen.findByTestId('routine-delete-r1'));
    await waitFor(() => expect(api.apagarRotina).toHaveBeenCalledWith('r1'));
    expect((await screen.findByTestId('routine-notice')).textContent).toContain('desfazer');
  });

  it('vazio e erro', async () => {
    api.listarRotinas.mockResolvedValueOnce({ rotinas: [], modelos: [foco] });
    render(<RoutinesPage />);
    expect((await screen.findByTestId('routines-empty')).textContent).toContain('Nenhuma rotina ainda');
    cleanup();

    api.listarRotinas.mockRejectedValue(new Error('Reinicie o servidor do Nicx para usar as rotinas.'));
    render(<RoutinesPage />);
    expect((await screen.findByRole('alert')).textContent).toContain('Reinicie o servidor');
  });
});
