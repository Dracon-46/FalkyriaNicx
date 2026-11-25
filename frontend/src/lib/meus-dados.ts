/**
 * Exportar todos os meus dados (`/v1/meus-dados/exportar`): o servidor monta um
 * .zip com o que o Nicx guarda no PC (sem segredos) e o app junta as conversas,
 * que ficam guardadas aqui no navegador.
 */
import { apiFetch } from './api';

/** Baixa o .zip; devolve o nome do arquivo. */
export async function exportarTudo(): Promise<string> {
  let conversas: unknown = null;
  try {
    conversas = JSON.parse(localStorage.getItem('nicx-conversations') || 'null');
  } catch {
    conversas = null;
  }
  const res = await apiFetch('/v1/meus-dados/exportar', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversas }),
  });
  if (!res.ok) throw new Error(String(res.status));
  const blob = await res.blob();
  const header = res.headers.get('Content-Disposition') ?? '';
  const nome = /filename="([^"]+)"/.exec(header)?.[1] ?? `nicx-meus-dados-${new Date().toISOString().slice(0, 10)}.zip`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = nome;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return nome;
}
