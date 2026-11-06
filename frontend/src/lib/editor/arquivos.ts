/**
 * Arquivos do editor pela API de arquivos do navegador (File System Access):
 * a pessoa escolhe a pasta, o navegador pede permissão e os arquivos nunca
 * passam pelo servidor do Nicx. Em navegador sem essa API (Firefox), abre um
 * arquivo por vez e "salvar" baixa o arquivo.
 */

export interface No {
  nome: string;
  /** Caminho relativo à pasta aberta ("src/app.py"). */
  caminho: string;
  tipo: 'arquivo' | 'pasta';
  handle?: FileSystemFileHandle | FileSystemDirectoryHandle;
}

export interface Aberto {
  caminho: string;
  nome: string;
  texto: string;
  /** Sem handle = aberto pelo <input type=file>: salvar baixa o arquivo. */
  handle?: FileSystemFileHandle;
}

/** Pastas que não aparecem na árvore (pesadas e não são do código da pessoa). */
export const IGNORADAS = new Set([
  'node_modules',
  '.git',
  '.venv',
  'venv',
  '__pycache__',
  'dist',
  'build',
  'out',
  'target',
  '.next',
  '.cache',
  '.idea',
  '.pytest_cache',
  '.mypy_cache',
  '.ruff_cache',
]);

/** Arquivos maiores que isso não abrem (e não iriam caber no modelo local). */
export const MAX_BYTES = 2 * 1024 * 1024;

type Janela = Window & {
  showDirectoryPicker?: (op?: { mode?: 'read' | 'readwrite' }) => Promise<FileSystemDirectoryHandle>;
};

export function temPastas(): boolean {
  return typeof (window as Janela).showDirectoryPicker === 'function';
}

export async function escolherPasta(): Promise<FileSystemDirectoryHandle | null> {
  const w = window as Janela;
  if (!w.showDirectoryPicker) return null;
  try {
    return await w.showDirectoryPicker({ mode: 'readwrite' });
  } catch (e) {
    if ((e as DOMException).name === 'AbortError') return null;
    throw e;
  }
}

/** Itens de uma pasta (só um nível; a árvore abre conforme a pessoa clica). */
export async function listar(pasta: FileSystemDirectoryHandle, base = ''): Promise<No[]> {
  const itens: No[] = [];
  // `values()` existe nos navegadores com a API; o tipo do TS ainda não tem.
  for await (const h of (pasta as unknown as { values(): AsyncIterable<FileSystemHandle> }).values()) {
    if (h.kind === 'directory' && IGNORADAS.has(h.name)) continue;
    itens.push({
      nome: h.name,
      caminho: base ? `${base}/${h.name}` : h.name,
      tipo: h.kind === 'directory' ? 'pasta' : 'arquivo',
      handle: h as FileSystemFileHandle | FileSystemDirectoryHandle,
    });
  }
  return itens.sort((a, b) => (a.tipo === b.tipo ? a.nome.localeCompare(b.nome) : a.tipo === 'pasta' ? -1 : 1));
}

function pareceBinario(texto: string): boolean {
  return texto.slice(0, 8000).includes('\u0000');
}

export class ArquivoGrande extends Error {}
export class ArquivoBinario extends Error {}

export async function ler(arquivo: File): Promise<string> {
  if (arquivo.size > MAX_BYTES) throw new ArquivoGrande(arquivo.name);
  const texto = await arquivo.text();
  if (pareceBinario(texto)) throw new ArquivoBinario(arquivo.name);
  return texto;
}

export async function abrir(no: No): Promise<Aberto> {
  const handle = no.handle as FileSystemFileHandle;
  return { caminho: no.caminho, nome: no.nome, texto: await ler(await handle.getFile()), handle };
}

/** Grava no disco (com a permissão da pasta) ou, sem handle, baixa o arquivo. */
export async function salvar(aberto: Aberto, texto: string): Promise<'gravado' | 'baixado'> {
  if (aberto.handle) {
    const permissao = aberto.handle as unknown as {
      queryPermission?: (op: { mode: string }) => Promise<string>;
      requestPermission?: (op: { mode: string }) => Promise<string>;
    };
    if (permissao.queryPermission && (await permissao.queryPermission({ mode: 'readwrite' })) !== 'granted') {
      if ((await permissao.requestPermission?.({ mode: 'readwrite' })) !== 'granted') {
        throw new DOMException('permissão negada', 'NotAllowedError');
      }
    }
    const saida = await aberto.handle.createWritable();
    await saida.write(texto);
    await saida.close();
    return 'gravado';
  }
  const url = URL.createObjectURL(new Blob([texto], { type: 'text/plain;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = aberto.nome;
  a.click();
  URL.revokeObjectURL(url);
  return 'baixado';
}
