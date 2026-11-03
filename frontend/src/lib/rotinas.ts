/**
 * Rotinas (`/v1/rotinas`): uma sequência de ações rápidas com nome, frases que
 * a disparam e, se quiser, um horário. Ficam só no PC.
 */
import { apiFetch } from './api';
import i18n from '../i18n';

export const WEEKDAYS = ['seg', 'ter', 'qua', 'qui', 'sex', 'sab', 'dom'] as const;

export type Weekday = (typeof WEEKDAYS)[number];

/** Tipos de passo que a rotina aceita (o servidor confirma em `/opcoes`). */
export const STEP_KINDS = [
  'volume',
  'media',
  'open',
  'open_url',
  'folder',
  'search',
  'youtube',
  'close',
  'note_add',
  'remind',
  'lock',
  'screenshot',
  'status',
  'time',
  'date',
  'battery',
  'resumo',
  'agenda_list',
  'remind_list',
] as const;

export type StepKind = (typeof STEP_KINDS)[number];

/** Texto do lembrete que o Nicx entende como timer simples. */
export const TIMER_TEXT = 'o tempo acabou';

export const MAX_STEPS = 20;
export const MAX_PHRASES = 5;
export const MAX_NAME = 60;

export interface RoutineStep {
  kind: string;
  op: string;
  /** Volume: passos (up/down) ou nível 0-100 (set). */
  value: number | null;
  target: string;
  site: string;
  /** Lembrete/timer: minutos a partir da hora em que a rotina roda. */
  minutos: number | null;
}

export interface RoutineSchedule {
  dias: Weekday[];
  /** "HH:MM" */
  hora: string;
}

export interface Routine {
  id: string;
  nome: string;
  passos: RoutineStep[];
  frases: string[];
  agenda: RoutineSchedule | null;
  ativa: boolean;
  criada_em: string;
  /** "" se nunca rodou. */
  ultima_execucao: string;
  ultimo_agendado: string;
  idioma: string;
}

export interface RoutineList {
  rotinas: Routine[];
  /** Modelos prontos (ex.: "modo foco", id "modelo-foco"), não salvos. */
  modelos: Routine[];
}

export interface RoutineOptions {
  tipos: string[];
  apps: { chave: string; rotulo: string }[];
  fechar: { chave: string; rotulo: string }[];
  pastas: string[];
}

export interface RoutineInput {
  nome: string;
  passos: RoutineStep[];
  frases?: string[];
  agenda?: RoutineSchedule | null;
  ativa?: boolean;
  idioma?: string;
}

export interface RunResult {
  ok: boolean;
  mensagem: string;
}

export interface Interpretation {
  passos: RoutineStep[];
  agenda: RoutineSchedule | null;
  /** Trechos da frase que o Nicx não entendeu. */
  nao_entendi: string[];
  /** Trechos que pedem passos proibidos em rotinas (desligar, apagar...). */
  proibidos: string[];
}

export const FOCUS_TEMPLATE_ID = 'modelo-foco';

async function detail(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    return typeof body.detail === 'string' ? body.detail : '';
  } catch {
    return '';
  }
}

async function json<T>(res: Response, failure: string): Promise<T> {
  if (res.status === 404) {
    // Servidor antigo: a rota não existe ("Not Found" genérico).
    const why = await detail(res);
    throw new Error(i18n.t(why && why !== 'Not Found' ? 'rotinas.notFound' : 'rotinas.restartServer'));
  }
  if (res.status === 405) throw new Error(i18n.t('rotinas.restartServer'));
  if (res.status === 409) throw new Error(i18n.t('rotinas.exists'));
  if (res.status === 400 || res.status === 422) {
    const why = await detail(res);
    throw new Error(why ? i18n.t('rotinas.invalid', { detail: why }) : i18n.t(failure));
  }
  if (!res.ok) throw new Error(i18n.t(failure));
  return res.json() as Promise<T>;
}

function send(path: string, method: string, body?: unknown): Promise<Response> {
  return apiFetch(path, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

const base = '/v1/rotinas';
const one = (id: string) => `${base}/${encodeURIComponent(id)}`;

export function emptyStep(kind: string = 'open'): RoutineStep {
  return { kind, op: '', value: null, target: '', site: '', minutos: null };
}

export async function listarRotinas(idioma?: string): Promise<RoutineList> {
  const query = idioma ? `?idioma=${encodeURIComponent(idioma)}` : '';
  return json(await apiFetch(`${base}${query}`), 'rotinas.loadFailed');
}

export async function opcoesRotinas(): Promise<RoutineOptions> {
  return json(await apiFetch(`${base}/opcoes`), 'rotinas.loadFailed');
}

export async function criarRotina(rotina: RoutineInput): Promise<Routine> {
  return json(await send(base, 'POST', rotina), 'rotinas.saveFailed');
}

export async function atualizarRotina(id: string, rotina: RoutineInput): Promise<Routine> {
  return json(await send(one(id), 'PUT', rotina), 'rotinas.saveFailed');
}

export async function apagarRotina(id: string): Promise<void> {
  await json(await send(one(id), 'DELETE'), 'rotinas.deleteFailed');
}

/** Roda agora (o id do modelo roda o modelo sem salvar). */
export async function executarRotina(id: string, idioma?: string): Promise<RunResult> {
  return json(await send(`${one(id)}/executar`, 'POST', { idioma }), 'rotinas.runFailed');
}

/** Lê uma descrição em linguagem natural; nada é salvo. */
export async function interpretarRotina(texto: string, idioma?: string): Promise<Interpretation> {
  return json(await send(`${base}/interpretar`, 'POST', { texto, idioma }), 'rotinas.interpretFailed');
}
