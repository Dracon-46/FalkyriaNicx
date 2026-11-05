import { apiFetch } from './api';
import i18n from '../i18n';

/**
 * Anexos do chat: imagens e vídeos que vão junto com a pergunta.
 *
 * - Imagem: reduzida aqui mesmo (lado de até 640 px, JPEG) e mandada em
 *   base64 no `images` da mensagem; o servidor confere de novo.
 * - Vídeo: vai para `/v1/anexos/video`, que devolve 4 quadros (imagens) e a
 *   transcrição do áudio pelo Whisper local. Nada sai do PC.
 *
 * As imagens não ficam guardadas nas conversas (o armazenamento do navegador
 * encheria): a conversa guarda só o tipo e o nome; as miniaturas valem
 * enquanto o app está aberto.
 */

export const MAX_IMAGENS = 4;
export const LADO = 640;
const LADO_MINIATURA = 160;

export type TipoAnexo = 'imagem' | 'video';

export interface Anexo {
  id: string;
  tipo: TipoAnexo;
  nome: string;
  /** data: URL pequena para mostrar no campo e na mensagem. */
  miniatura: string;
  /** Base64 sem o prefixo data:, já reduzidas. */
  imagens: string[];
  transcricao?: string;
  duracao?: number;
  preparando?: boolean;
}

/** O que a conversa guarda de cada anexo (sem as imagens). */
export interface AnexoSalvo {
  tipo: TipoAnexo;
  nome: string;
}

let contador = 0;
const novoId = () => `anexo-${Date.now().toString(36)}-${(contador++).toString(36)}`;

export function tipoDoArquivo(arquivo: File): TipoAnexo | null {
  if (arquivo.type.startsWith('image/')) return 'imagem';
  if (arquivo.type.startsWith('video/')) return 'video';
  const ext = arquivo.name.toLowerCase().split('.').pop() ?? '';
  if (['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp'].includes(ext)) return 'imagem';
  if (['mp4', 'mov', 'mkv', 'webm', 'avi', 'm4v'].includes(ext)) return 'video';
  return null;
}

async function desenhar(fonte: CanvasImageSource, largura: number, altura: number, lado: number, qualidade = 0.85): Promise<string> {
  const escala = Math.min(1, lado / Math.max(largura, altura));
  const w = Math.max(1, Math.round(largura * escala));
  const h = Math.max(1, Math.round(altura * escala));
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error(i18n.t('chat.attach.imageFailed'));
  // Fundo branco: PNG transparente não vira preto no JPEG.
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, w, h);
  ctx.drawImage(fonte, 0, 0, w, h);
  return canvas.toDataURL('image/jpeg', qualidade);
}

const semPrefixo = (dataUrl: string) => dataUrl.slice(dataUrl.indexOf(',') + 1);

/** Imagem do arquivo (ou colada) reduzida para o modelo, mais a miniatura. */
export async function prepararImagem(arquivo: Blob, nome: string): Promise<Anexo> {
  let bitmap: ImageBitmap;
  try {
    // 'from-image': foto de celular "de lado" fica em pé (EXIF).
    bitmap = await createImageBitmap(arquivo, { imageOrientation: 'from-image' });
  } catch {
    throw new Error(i18n.t('chat.attach.imageFailed'));
  }
  try {
    const grande = await desenhar(bitmap, bitmap.width, bitmap.height, LADO);
    const miniatura = await desenhar(bitmap, bitmap.width, bitmap.height, LADO_MINIATURA, 0.7);
    return { id: novoId(), tipo: 'imagem', nome, miniatura, imagens: [semPrefixo(grande)] };
  } finally {
    bitmap.close();
  }
}

/** Anexo de vídeo ainda sem os quadros (o campo mostra "preparando"). */
export function videoPendente(arquivo: File): Anexo {
  return { id: novoId(), tipo: 'video', nome: arquivo.name, miniatura: '', imagens: [], preparando: true };
}

interface RespostaVideo {
  quadros: string[];
  duracao: number;
  tem_audio: boolean;
  transcricao: string;
  transcrito: boolean;
}

/** Manda o vídeo ao servidor local: volta com os quadros e a transcrição. */
export async function prepararVideo(arquivo: File, anexo: Anexo, signal?: AbortSignal): Promise<Anexo> {
  const corpo = new FormData();
  corpo.append('arquivo', arquivo, arquivo.name);
  corpo.append('idioma', i18n.language);
  const res = await apiFetch('/v1/anexos/video', { method: 'POST', body: corpo, signal });
  if (!res.ok) {
    let detalhe = String(res.status);
    try {
      const j = (await res.json()) as { detail?: unknown };
      if (typeof j.detail === 'string') detalhe = j.detail;
    } catch {
      // sem JSON
    }
    throw new Error(i18n.t('chat.attach.videoFailed', { detail: detalhe }));
  }
  const dados = (await res.json()) as RespostaVideo;
  const primeira = dados.quadros[0];
  return {
    ...anexo,
    preparando: false,
    imagens: dados.quadros,
    transcricao: dados.transcricao,
    duracao: dados.duracao,
    miniatura: primeira ? `data:image/jpeg;base64,${primeira}` : '',
  };
}

export const contarImagens = (anexos: Anexo[]) => anexos.reduce((n, a) => n + (a.tipo === 'video' ? MAX_IMAGENS : a.imagens.length || 1), 0);

/**
 * O texto que vai ao modelo: o que a pessoa escreveu (ou uma pergunta padrão)
 * e a fala de cada vídeo. A tela mostra só o que ela escreveu.
 */
export function textoParaModelo(texto: string, anexos: Anexo[]): string {
  const temVideo = anexos.some((a) => a.tipo === 'video');
  let base = texto.trim();
  if (!base) base = i18n.t(temVideo ? 'chat.attach.videoPrompt' : 'chat.attach.imagePrompt');
  const falas = anexos
    .filter((a) => a.tipo === 'video')
    .map((a) => {
      const cabeca = i18n.t('chat.attach.videoInfo', { name: a.nome, seconds: Math.round(a.duracao ?? 0) });
      const fala = a.transcricao ? `\n${i18n.t('chat.attach.videoAudio')}: ${a.transcricao}` : '';
      return `\n\n[${cabeca}${fala}]`;
    });
  return base + falas.join('');
}

// Miniaturas por mensagem, só enquanto o app está aberto.
const miniaturas = new Map<string, string[]>();

export function guardarMiniaturas(mensagemId: string, anexos: Anexo[]): void {
  const lista = anexos.map((a) => a.miniatura).filter(Boolean);
  if (lista.length) miniaturas.set(mensagemId, lista);
}

export function miniaturasDa(mensagemId: string): string[] {
  return miniaturas.get(mensagemId) ?? [];
}
