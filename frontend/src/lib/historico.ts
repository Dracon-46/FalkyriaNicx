/**
 * Histórico universal (`/v1/historico`): tudo o que o Nicx fez, com desfazer
 * e auditoria, e o nível de autonomia (`/v1/autonomia`). Fica só no PC
 * (`~/.nicx/historico.db`).
 */
import { apiFetch } from './api';
import i18n from '../i18n';

export const ACTIVITY_TYPES = [
  'conversa',
  'nota',
  'lembrete',
  'agenda',
  'projeto',
  'arquivo',
  'organizacao',
  'acao',
  'ferramenta',
  'desfazer',
  'rotina',
  'assistente',
] as const;

export type ActivityType = (typeof ACTIVITY_TYPES)[number];

export type ActivityResult = 'ok' | 'falhou' | 'bloqueado' | 'pendente';

export const AUTONOMY_LEVELS = ['observador', 'assistido', 'autonomo'] as const;

export type AutonomyLevel = (typeof AUTONOMY_LEVELS)[number];

export type Risk = 'leitura' | 'leve' | 'moderado' | 'alto';

export interface Activity {
  id: number;
  /** ISO local, ex.: "2026-10-30T14:05:11". */
  quando: string;
  tipo: ActivityType;
  /** Já legível, no idioma em que aconteceu. */
  titulo: string;
  /** "chat", "voz", "app", "agente"... */
  origem: string;
  resultado: ActivityResult;
  /** Nível de autonomia na hora ("" quando não se aplica). */
  nivel: '' | AutonomyLevel;
  /** Ferramenta: {ferramenta, argumentos, resposta, risco}; ação: {acao, op, alvo, risco}. */
  detalhe: Record<string, unknown>;
  desfazivel: boolean;
  desfeito_em: string | null;
}

export interface ActivityPage {
  itens: Activity[];
  mais: boolean;
}

export interface ActivityFilter {
  busca?: string;
  tipos?: string[];
  /** AAAA-MM-DD */
  desde?: string;
  /** AAAA-MM-DD */
  ate?: string;
  soDesfaziveis?: boolean;
  limite?: number;
  antesDe?: number;
}

export interface UndoResult {
  ok: boolean;
  mensagem: string;
}

export interface Integrity {
  ok: boolean;
  linhas: number;
  /** Id da primeira atividade cuja cadeia não confere. */
  quebra_em: number | null;
}

export interface AutonomyState {
  nivel: AutonomyLevel;
  niveis: { nivel: AutonomyLevel; liberado: Risk[] }[];
  riscos: Risk[];
}

async function json<T>(res: Response, failure: string): Promise<T> {
  if (res.status === 404 || res.status === 405) throw new Error(i18n.t('historico.restartServer'));
  if (!res.ok) throw new Error(i18n.t(failure));
  return res.json() as Promise<T>;
}

function send(path: string, method: string, body: unknown): Promise<Response> {
  return apiFetch(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function listarHistorico(filter: ActivityFilter = {}): Promise<ActivityPage> {
  const params = new URLSearchParams();
  if (filter.busca?.trim()) params.set('busca', filter.busca.trim());
  if (filter.tipos?.length) params.set('tipos', filter.tipos.join(','));
  if (filter.desde) params.set('desde', filter.desde);
  if (filter.ate) params.set('ate', filter.ate);
  if (filter.soDesfaziveis) params.set('so_desfaziveis', 'true');
  if (filter.limite) params.set('limite', String(filter.limite));
  if (filter.antesDe !== undefined) params.set('antes_de', String(filter.antesDe));
  const query = params.toString();
  return json(await apiFetch(query ? `/v1/historico?${query}` : '/v1/historico'), 'historico.loadFailed');
}

/** Desfaz a atividade `id` (sem id: a última que dá). A mensagem vem no idioma pedido. */
export async function desfazerAtividade(id?: number, idioma?: string): Promise<UndoResult> {
  return json(await send('/v1/historico/desfazer', 'POST', { id, idioma }), 'historico.undoFailed');
}

export async function verificarIntegridade(): Promise<Integrity> {
  return json(await apiFetch('/v1/historico/integridade'), 'historico.loadFailed');
}

export async function obterAutonomia(): Promise<AutonomyState> {
  return json(await apiFetch('/v1/autonomia'), 'settings.autonomy.loadFailed');
}

export async function salvarAutonomia(nivel: AutonomyLevel): Promise<AutonomyState> {
  return json(await send('/v1/autonomia', 'PUT', { nivel }), 'settings.autonomy.saveFailed');
}
