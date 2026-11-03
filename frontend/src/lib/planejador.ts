/**
 * Planejador de objetivos (`/v1/planejador`): o modelo local propõe etapas
 * para um objetivo com prazo e o plano vira um projeto com datas e lembretes.
 */
import { apiFetch } from './api';
import i18n from '../i18n';

export interface ProposedStep {
  texto: string;
  minutos: number;
  /** Índices de etapas anteriores das quais esta depende. */
  depende_de: number[];
}

export interface Proposal {
  etapas: ProposedStep[];
  /** AAAA-MM-DD */
  prazo: string;
}

export interface StepRef {
  id: string;
  texto: string;
  prazo: string;
}

export interface PlanProgress {
  projeto: string;
  nome: string;
  /** AAAA-MM-DD ou "" (projeto sem prazo). */
  prazo: string;
  dias_restantes: number | null;
  total: number;
  feitas: number;
  percentual: number;
  minutos_total: number;
  minutos_feitos: number;
  atrasadas: StepRef[];
  proxima: StepRef | null;
  no_ritmo: boolean;
}

export interface CreatedPlan {
  projeto: { id: string; nome: string; prazo: string } & Record<string, unknown>;
  progresso: PlanProgress;
}

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
    const why = await detail(res);
    throw new Error(i18n.t(why && why !== 'Not Found' ? 'planejador.notFound' : 'planejador.restartServer'));
  }
  if (res.status === 405) throw new Error(i18n.t('planejador.restartServer'));
  if (res.status === 503) throw new Error(i18n.t('planejador.noLocalModel'));
  if (res.status === 422) throw new Error(i18n.t('planejador.nothingUsable'));
  if (res.status === 400) {
    const why = await detail(res);
    throw new Error(why ? i18n.t('planejador.invalid', { detail: why }) : i18n.t(failure));
  }
  if (!res.ok) throw new Error(i18n.t(failure));
  return res.json() as Promise<T>;
}

function send(path: string, body: unknown, signal?: AbortSignal): Promise<Response> {
  return apiFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
}

const base = '/v1/planejador';

/** Pode levar 30-90 s no modelo local: passe um `signal` para cancelar. */
export async function proporEtapas(
  objetivo: string,
  prazo: string,
  idioma?: string,
  signal?: AbortSignal,
): Promise<Proposal> {
  return json(await send(`${base}/propor`, { objetivo, prazo, idioma }, signal), 'planejador.proposeFailed');
}

export async function criarPlano(plano: {
  objetivo: string;
  prazo: string;
  etapas: ProposedStep[];
  nome?: string;
  idioma?: string;
}): Promise<CreatedPlan> {
  return json(await send(base, plano), 'planejador.createFailed');
}

export async function obterProgresso(projetoId: string): Promise<PlanProgress> {
  return json(await apiFetch(`${base}/${encodeURIComponent(projetoId)}`), 'planejador.loadFailed');
}

export async function reajustarPlano(projetoId: string, prazo?: string): Promise<PlanProgress> {
  return json(
    await send(`${base}/${encodeURIComponent(projetoId)}/reajustar`, prazo ? { prazo } : {}),
    'planejador.adjustFailed',
  );
}

/** "até dezembro" -> "2026-12-31" (ou null se não deu para entender). */
export async function interpretarPrazo(texto: string): Promise<string | null> {
  const res = await json<{ prazo: string | null }>(await send(`${base}/prazo`, { texto }), 'planejador.deadlineFailed');
  return res.prazo;
}
