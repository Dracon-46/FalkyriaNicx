/**
 * Partes da extensão que não dependem do VS Code (testadas com vitest):
 * os pedidos ao Nicx, a leitura da resposta em partes (SSE) e o código que
 * volta numa resposta.
 */

export type Acao = 'explicar' | 'corrigir' | 'melhorar' | 'testes' | 'perguntar';

export interface Trecho {
  /** Caminho relativo ao projeto, só para o modelo saber de onde é. */
  arquivo: string;
  linguagem: string;
  /** O que está selecionado (ou o arquivo inteiro, se pequeno). */
  codigo: string;
  /** Linhas em volta, para dar contexto (não são alteradas). */
  antes?: string;
  depois?: string;
  /** Problemas que o VS Code mostra no trecho (erros e avisos). */
  problemas?: string[];
  /** Linha da primeira linha do trecho (1 = primeira do arquivo). */
  linhaInicial?: number;
}

export interface Mensagem {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

/** Limite de caracteres que vão ao modelo local (cabe no num_ctx 8192). */
export const MAX_CODIGO = 12000;

export const SISTEMA =
  'Você é o Nicx, a IA da Falkyria, ajudando dentro do VS Code. Responda em português do Brasil, ' +
  'direto ao ponto. Quando devolver código, use um único bloco ``` com a linguagem certa e o trecho ' +
  'completo pronto para substituir o original, sem "...", sem explicar linha por linha dentro do bloco.';

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
export const ACOES_COM_PROPOSTA: ReadonlySet<Acao> = new Set(['corrigir', 'melhorar']);

function cortar(texto: string, max: number): string {
  return texto.length <= max ? texto : `${texto.slice(0, max)}\n… (cortado)`;
}

export function blocoDoTrecho(t: Trecho): string {
  const cerca = t.codigo.includes('```') ? '~~~~' : '```';
  const partes = [`Arquivo: ${t.arquivo} (${t.linguagem})`];
  if (t.linhaInicial) partes.push(`Começa na linha ${t.linhaInicial}.`);
  if (t.antes) partes.push(`Antes do trecho (só contexto, não altere):\n${cerca}${t.linguagem}\n${cortar(t.antes, 3000)}\n${cerca}`);
  partes.push(`Trecho:\n${cerca}${t.linguagem}\n${cortar(t.codigo, MAX_CODIGO)}\n${cerca}`);
  if (t.depois) partes.push(`Depois do trecho (só contexto, não altere):\n${cerca}${t.linguagem}\n${cortar(t.depois, 3000)}\n${cerca}`);
  if (t.problemas?.length) partes.push(`Problemas que o editor mostra:\n${t.problemas.slice(0, 20).map((p) => `- ${p}`).join('\n')}`);
  return partes.join('\n\n');
}

/** A mensagem do usuário para uma ação sobre um trecho. */
export function pedido(acao: Acao, t: Trecho, pergunta = ''): string {
  const instrucao = acao === 'perguntar' ? pergunta.trim() || 'O que você acha deste trecho?' : PEDIDOS[acao];
  return `${instrucao}\n\n${blocoDoTrecho(t)}`;
}

/** O primeiro bloco de código da resposta (ou null). */
export function extrairCodigo(resposta: string): string | null {
  const m = resposta.match(/(```+|~~~+)[^\n]*\n([\s\S]*?)\n?\1/);
  if (!m) return null;
  return m[2];
}

/**
 * Mantém o recuo do original: o modelo às vezes devolve o trecho sem a
 * indentação da primeira linha selecionada.
 */
export function ajustarRecuo(original: string, proposta: string): string {
  const recuo = (s: string) => (s.match(/^[ \t]*/) ?? [''])[0];
  const primeiraOriginal = original.split('\n').find((l) => l.trim()) ?? '';
  const primeiraProposta = proposta.split('\n').find((l) => l.trim()) ?? '';
  const ro = recuo(primeiraOriginal);
  const rp = recuo(primeiraProposta);
  if (!ro || rp.length >= ro.length) return proposta;
  const falta = ro.slice(rp.length);
  return proposta
    .split('\n')
    .map((l) => (l.trim() ? falta + l : l))
    .join('\n');
}

/** Só o Nicx deste PC: http(s) num endereço local. */
export function servidorLocal(url: string): URL {
  let u: URL;
  try {
    u = new URL(url);
  } catch {
    throw new Error(`Endereço do Nicx inválido: ${url}`);
  }
  const locais = new Set(['127.0.0.1', 'localhost', '[::1]', '::1']);
  if (!['http:', 'https:'].includes(u.protocol) || !locais.has(u.hostname)) {
    throw new Error('A extensão só conversa com o Nicx deste computador (127.0.0.1).');
  }
  return u;
}

/**
 * Lê a resposta em partes do `/v1/chat/completions` (SSE, formato OpenAI):
 * devolve o texto de cada pedaço. Linhas `event:` do Nicx (agente) são
 * ignoradas; `[DONE]` termina.
 */
export async function* lerPartes(corpo: AsyncIterable<Uint8Array>): AsyncGenerator<string> {
  const decodificador = new TextDecoder();
  let resto = '';
  for await (const pedaco of corpo) {
    resto += decodificador.decode(pedaco, { stream: true });
    const linhas = resto.split('\n');
    resto = linhas.pop() ?? '';
    for (const linha of linhas) {
      const texto = textoDaLinha(linha);
      if (texto === null) continue;
      if (texto === FIM) return;
      if (texto) yield texto;
    }
  }
  const ultima = textoDaLinha(resto);
  if (ultima && ultima !== FIM) yield ultima;
}

const FIM = '\u0000fim';

function textoDaLinha(linha: string): string | null {
  const l = linha.trim();
  if (!l.startsWith('data:')) return null;
  const dados = l.slice(5).trim();
  if (dados === '[DONE]') return FIM;
  try {
    const j = JSON.parse(dados) as { choices?: Array<{ delta?: { content?: unknown } }>; error?: unknown };
    if (j.error) throw new Error(typeof j.error === 'string' ? j.error : JSON.stringify(j.error));
    const c = j.choices?.[0]?.delta?.content;
    return typeof c === 'string' ? c : '';
  } catch (e) {
    if (e instanceof SyntaxError) return '';
    throw e;
  }
}
