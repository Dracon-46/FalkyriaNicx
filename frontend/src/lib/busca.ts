/**
 * Pesquisar em tudo: o servidor busca em projetos, notas, lembretes, agenda,
 * memória, histórico e tarefas (`/v1/busca`); as conversas ficam no app e são
 * buscadas aqui, do mesmo jeito (sem acento, todas as palavras).
 */
import { apiFetch } from './api';
import type { Conversation } from '../types';

export type SearchSource =
  | 'conversa'
  | 'projeto'
  | 'nota'
  | 'lembrete'
  | 'compromisso'
  | 'memoria'
  | 'historico'
  | 'trabalho';

export interface SearchHit {
  fonte: SearchSource;
  titulo: string;
  trecho: string;
  /** ISO ou "". */
  quando: string;
  link: string;
  ref: string;
  pontos: number;
  extra: Record<string, unknown>;
}

export function normalizar(texto: string): string {
  return (texto || '').normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

export function palavras(busca: string): string[] {
  return (normalizar(busca).match(/[\p{L}\p{N}_]+/gu) ?? []).filter((p) => p.length >= 2);
}

function contar(texto: string, termos: string[]): number {
  const t = normalizar(texto);
  let total = 0;
  for (const termo of termos) {
    let n = 0;
    for (let i = t.indexOf(termo); i >= 0; i = t.indexOf(termo, i + termo.length)) n++;
    if (!n) return 0;
    total += n;
  }
  return total;
}

export function trecho(texto: string, termos: string[], tamanho = 180): string {
  const limpo = (texto || '').split(/\s+/).join(' ').trim();
  if (limpo.length <= tamanho) return limpo;
  const t = normalizar(limpo);
  const posicoes = termos.map((x) => t.indexOf(x)).filter((i) => i >= 0);
  const pos = posicoes.length ? Math.min(...posicoes) : 0;
  const inicio = Math.max(0, pos - Math.floor(tamanho / 3));
  const fim = Math.min(limpo.length, inicio + tamanho);
  return (inicio ? '…' : '') + limpo.slice(inicio, fim).trim() + (fim < limpo.length ? '…' : '');
}

/** Conversas que têm todas as palavras (no título ou nas mensagens). */
export function buscarConversas(conversas: Conversation[], busca: string, limite = 20): SearchHit[] {
  const termos = palavras(busca);
  if (!termos.length) return [];
  const achados: SearchHit[] = [];
  for (const c of conversas) {
    const corpo = c.messages.map((m) => m.content || '').join('\n');
    const pontos = contar(`${c.title}\n${corpo}`, termos) + 2 * contar(c.title, termos);
    if (!pontos) continue;
    const mensagem = c.messages.find((m) => contar(m.content || '', termos) > 0);
    achados.push({
      fonte: 'conversa',
      titulo: c.title,
      trecho: trecho(mensagem?.content ?? '', termos),
      quando: new Date(c.updatedAt).toISOString(),
      link: '/',
      ref: c.id,
      pontos,
      extra: {},
    });
  }
  return achados.sort((a, b) => b.pontos - a.pontos || b.quando.localeCompare(a.quando)).slice(0, limite);
}

export async function buscarNoServidor(busca: string, signal?: AbortSignal): Promise<{ resultados: SearchHit[]; falharam: string[] }> {
  const res = await apiFetch(`/v1/busca?q=${encodeURIComponent(busca)}`, { signal });
  if (!res.ok) throw new Error(String(res.status));
  return res.json();
}
