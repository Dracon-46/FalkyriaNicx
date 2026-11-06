import { streamChat } from '../sse';

/**
 * O Nicx no editor do app: os mesmos pedidos da extensão do VS Code
 * (vscode/src/nucleo.ts; mudou lá, mude aqui). Vão com `editor: true`:
 * direto ao modelo, sem ferramentas do PC, e o código fica fora da memória.
 */

export type Acao = 'explicar' | 'corrigir' | 'melhorar' | 'testes' | 'perguntar';

export interface Trecho {
  arquivo: string;
  linguagem: string;
  codigo: string;
  antes?: string;
  depois?: string;
  linhaInicial?: number;
}

export const MAX_CODIGO = 12000;

export const SISTEMA =
  'Você é o Nicx, a IA da Falkyria, ajudando no editor de código do app. Responda direto ao ponto. ' +
  'Quando devolver código, use um único bloco ``` com a linguagem certa e o trecho completo pronto para ' +
  'substituir o original, sem "...", sem explicar linha por linha dentro do bloco.';

const PEDIDOS: Record<Exclude<Acao, 'perguntar'>, string> = {
  explicar: 'Explique o que este trecho faz, em poucas frases, e aponte qualquer problema que você ver.',
  corrigir:
    'Corrija os erros deste trecho. Devolva o trecho inteiro corrigido em um bloco ``` e, depois do bloco, ' +
    'diga em uma ou duas frases o que mudou.',
  melhorar:
    'Melhore este trecho (clareza, nomes, desempenho), sem mudar o comportamento. Devolva o trecho inteiro ' +
    'em um bloco ``` e, depois, diga em uma ou duas frases o que mudou.',
  testes:
    'Escreva testes para este trecho, no framework de testes mais comum para a linguagem. Devolva só os ' +
    'testes em um bloco ```.',
};

/** Ações que devolvem um trecho para substituir a seleção (vão para o diff). */
export const COM_PROPOSTA: ReadonlySet<Acao> = new Set(['corrigir', 'melhorar']);

function cortar(texto: string, max: number): string {
  return texto.length <= max ? texto : `${texto.slice(0, max)}\n… (cortado)`;
}

export function pedido(acao: Acao, t: Trecho, pergunta = ''): string {
  const instrucao = acao === 'perguntar' ? pergunta.trim() || 'O que você acha deste trecho?' : PEDIDOS[acao];
  const cerca = t.codigo.includes('```') ? '~~~~' : '```';
  const partes = [instrucao, `Arquivo: ${t.arquivo} (${t.linguagem})`];
  if (t.linhaInicial) partes.push(`Começa na linha ${t.linhaInicial}.`);
  if (t.antes) partes.push(`Antes do trecho (só contexto, não altere):\n${cerca}${t.linguagem}\n${cortar(t.antes, 3000)}\n${cerca}`);
  partes.push(`Trecho:\n${cerca}${t.linguagem}\n${cortar(t.codigo, MAX_CODIGO)}\n${cerca}`);
  if (t.depois) partes.push(`Depois do trecho (só contexto, não altere):\n${cerca}${t.linguagem}\n${cortar(t.depois, 3000)}\n${cerca}`);
  return partes.join('\n\n');
}

export function extrairCodigo(resposta: string): string | null {
  const m = resposta.match(/(```+|~~~+)[^\n]*\n([\s\S]*?)\n?\1/);
  return m ? m[2] : null;
}

export function ajustarRecuo(original: string, proposta: string): string {
  const recuo = (s: string) => (s.match(/^[ \t]*/) ?? [''])[0];
  const ro = recuo(original.split('\n').find((l) => l.trim()) ?? '');
  const rp = recuo(proposta.split('\n').find((l) => l.trim()) ?? '');
  if (!ro || rp.length >= ro.length) return proposta;
  const falta = ro.slice(rp.length);
  return proposta
    .split('\n')
    .map((l) => (l.trim() ? falta + l : l))
    .join('\n');
}

/** Linguagem pelo nome do arquivo (para o modelo e para as cores). */
export function linguagemDe(nome: string): string {
  const ext = nome.toLowerCase().split('.').pop() ?? '';
  const mapa: Record<string, string> = {
    py: 'python', ts: 'typescript', tsx: 'tsx', js: 'javascript', jsx: 'jsx', mjs: 'javascript', cjs: 'javascript',
    json: 'json', html: 'html', htm: 'html', css: 'css', scss: 'scss', md: 'markdown', sql: 'sql', rs: 'rust',
    go: 'go', java: 'java', kt: 'kotlin', cs: 'csharp', c: 'c', h: 'c', cpp: 'cpp', hpp: 'cpp', php: 'php',
    rb: 'ruby', sh: 'bash', ps1: 'powershell', yml: 'yaml', yaml: 'yaml', toml: 'toml', xml: 'xml', vue: 'vue',
    dart: 'dart', swift: 'swift', lua: 'lua', r: 'r',
  };
  return mapa[ext] ?? (ext || 'texto');
}

/** A resposta do Nicx, pedaço por pedaço. */
export async function* conversar(
  mensagens: Array<{ role: 'user' | 'assistant'; content: string }>,
  modelo: string,
  signal?: AbortSignal,
): AsyncGenerator<string> {
  for await (const evento of streamChat(
    {
      model: modelo,
      stream: true,
      editor: true,
      temperature: 0.2,
      max_tokens: 2048,
      messages: [{ role: 'system', content: SISTEMA }, ...mensagens],
    },
    signal,
  )) {
    if (evento.event) continue; // eventos do agente (não vêm no modo editor)
    try {
      const j = JSON.parse(evento.data) as { choices?: Array<{ delta?: { content?: unknown } }>; error?: unknown };
      if (j.error) throw new Error(typeof j.error === 'string' ? j.error : JSON.stringify(j.error));
      const c = j.choices?.[0]?.delta?.content;
      if (typeof c === 'string' && c) yield c;
    } catch (e) {
      if (e instanceof SyntaxError) continue;
      throw e;
    }
  }
}
