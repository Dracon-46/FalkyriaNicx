// ---------------------------------------------------------------------------
// Resumo do dia: o texto de hoje e o resumo automático ([resumo] no config.toml)
// ---------------------------------------------------------------------------

import i18n from '../i18n';
import { apiFetch } from './api';

export type DailySummaryDay = 'seg' | 'ter' | 'qua' | 'qui' | 'sex' | 'sab' | 'dom';

export const DAILY_SUMMARY_DAYS: DailySummaryDay[] = ['seg', 'ter', 'qua', 'qui', 'sex', 'sab', 'dom'];

export interface DailySummaryConfig {
  ativo: boolean;
  /** "HH:MM", hora local. */
  hora: string;
  falar: boolean;
  notificar: boolean;
  dias: DailySummaryDay[];
  opcoes_dias: DailySummaryDay[];
  /** Data (AAAA-MM-DD) do último resumo automático, ou null. */
  ultimo_envio: string | null;
}

export type DailySummaryUpdate = Partial<Pick<DailySummaryConfig, 'ativo' | 'hora' | 'falar' | 'notificar' | 'dias'>>;

export interface DailySummary {
  dia: string;
  idioma: string;
  texto: string;
  texto_pendente: string;
  /** true quando o modelo local reescreveu o texto. */
  refinado: boolean;
}

async function configResponse(res: Response): Promise<DailySummaryConfig> {
  if (res.status === 404 || res.status === 405) throw new Error(i18n.t('settings.dailySummary.restartServer'));
  if (!res.ok) throw new Error(i18n.t('settings.dailySummary.saveFailed'));
  return res.json();
}

export async function fetchDailySummaryConfig(): Promise<DailySummaryConfig> {
  return configResponse(await apiFetch(`/v1/resumo/config`));
}

export async function updateDailySummaryConfig(update: DailySummaryUpdate): Promise<DailySummaryConfig> {
  return configResponse(
    await apiFetch(`/v1/resumo/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(update),
    }),
  );
}

/** O resumo de hoje no idioma da interface; `refine` pede o modelo local (lento). */
export async function fetchDailySummary(language: string, refine = false): Promise<DailySummary> {
  const params = new URLSearchParams({ idioma: language });
  if (refine) params.set('refinar', 'true');
  const res = await apiFetch(`/v1/resumo?${params.toString()}`);
  if (res.status === 404 || res.status === 405) throw new Error(i18n.t('settings.dailySummary.restartServer'));
  if (!res.ok) throw new Error(i18n.t('settings.dailySummary.loadFailed'));
  return res.json();
}
