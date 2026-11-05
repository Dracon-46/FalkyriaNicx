import { describe, expect, it } from 'vitest';
import { ajustarRecuo, blocoDoTrecho, extrairCodigo, lerPartes, pedido, servidorLocal } from './nucleo';

async function* corpo(...partes: string[]): AsyncGenerator<Uint8Array> {
  const enc = new TextEncoder();
  for (const p of partes) yield enc.encode(p);
}

async function juntar(gerador: AsyncGenerator<string>): Promise<string> {
  let s = '';
  for await (const p of gerador) s += p;
  return s;
}

const chunk = (texto: string) => `data: ${JSON.stringify({ choices: [{ delta: { content: texto } }] })}\n\n`;

describe('lerPartes', () => {
  it('junta os pedaços e para no [DONE]', async () => {
    const r = await juntar(lerPartes(corpo(chunk('Olá'), chunk(', mundo'), 'data: [DONE]\n\n', chunk('depois'))));
    expect(r).toBe('Olá, mundo');
  });

  it('linha partida entre dois pedaços de rede', async () => {
    const linha = chunk('inteiro');
    const r = await juntar(lerPartes(corpo(linha.slice(0, 10), linha.slice(10))));
    expect(r).toBe('inteiro');
  });

  it('ignora eventos do agente e linhas sem dados', async () => {
    const r = await juntar(
      lerPartes(corpo('event: tool_call_start\ndata: {"tool":"x"}\n\n', ': ping\n', chunk('ok'))),
    );
    expect(r).toBe('ok');
  });

  it('erro do servidor dentro do stream vira exceção', async () => {
    await expect(juntar(lerPartes(corpo('data: {"error":"Ollama caiu"}\n\n')))).rejects.toThrow('Ollama caiu');
  });
});

describe('pedidos', () => {
  const trecho = { arquivo: 'src/a.py', linguagem: 'python', codigo: 'def f():\n    return 1\n', problemas: ['linha 2: x'], linhaInicial: 10 };

  it('leva o arquivo, a linguagem, a linha e os problemas', () => {
    const p = pedido('corrigir', trecho);
    expect(p).toContain('Corrija os erros');
    expect(p).toContain('Arquivo: src/a.py (python)');
    expect(p).toContain('Começa na linha 10.');
    expect(p).toContain('- linha 2: x');
    expect(p).toContain('```python\ndef f():');
  });

  it('pergunta livre usa o texto da pessoa', () => {
    expect(pedido('perguntar', trecho, 'por que retorna 1?')).toMatch(/^por que retorna 1\?/);
  });

  it('código com ``` usa outra cerca', () => {
    expect(blocoDoTrecho({ ...trecho, codigo: 'x = "```"' })).toContain('~~~~python');
  });
});

describe('extrairCodigo e ajustarRecuo', () => {
  it('pega o primeiro bloco', () => {
    expect(extrairCodigo('Pronto:\n```python\nx = 1\ny = 2\n```\nMudei o x.')).toBe('x = 1\ny = 2');
    expect(extrairCodigo('~~~js\nlet a\n~~~')).toBe('let a');
    expect(extrairCodigo('sem código')).toBeNull();
  });

  it('devolve o recuo que o modelo tirou', () => {
    const original = '    if x:\n        y()\n';
    expect(ajustarRecuo(original, 'if x:\n    y()')).toBe('    if x:\n        y()');
    expect(ajustarRecuo(original, '    if x:\n        z()')).toBe('    if x:\n        z()');
  });
});

describe('servidorLocal', () => {
  it('só o Nicx deste PC', () => {
    expect(servidorLocal('http://127.0.0.1:8000').port).toBe('8000');
    expect(servidorLocal('http://localhost:8765').hostname).toBe('localhost');
    expect(() => servidorLocal('https://exemplo.com')).toThrow('deste computador');
    expect(() => servidorLocal('http://192.168.0.5:8000')).toThrow('deste computador');
    expect(() => servidorLocal('ftp://127.0.0.1')).toThrow();
    expect(() => servidorLocal('não é url')).toThrow('inválido');
  });
});
