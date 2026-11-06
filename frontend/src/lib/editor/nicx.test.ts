import { describe, expect, it, vi } from 'vitest';

const sse = vi.hoisted(() => ({ streamChat: vi.fn() }));
vi.mock('../sse', () => sse);

import { ajustarRecuo, conversar, extrairCodigo, linguagemDe, pedido } from './nicx';

describe('editor: pedido ao Nicx', () => {
  const trecho = { arquivo: 'src/a.py', linguagem: 'python', codigo: 'x = 1\n', linhaInicial: 3, antes: 'import os\n' };

  it('leva a instrução, o arquivo e o contexto', () => {
    const p = pedido('melhorar', trecho);
    expect(p).toMatch(/^Melhore este trecho/);
    expect(p).toContain('Arquivo: src/a.py (python)');
    expect(p).toContain('Começa na linha 3.');
    expect(p).toContain('Antes do trecho (só contexto, não altere):');
  });

  it('extrai o código e devolve o recuo', () => {
    expect(extrairCodigo('ok\n```py\na = 2\n```\nmudei')).toBe('a = 2');
    expect(extrairCodigo('nada')).toBeNull();
    expect(ajustarRecuo('  if x:\n    y()\n', 'if x:\n  y()')).toBe('  if x:\n    y()');
  });

  it('linguagem pelo nome do arquivo', () => {
    expect(linguagemDe('app.tsx')).toBe('tsx');
    expect(linguagemDe('main.py')).toBe('python');
    expect(linguagemDe('LEIAME')).toBe('leiame');
  });
});

describe('editor: conversar', () => {
  it('manda editor: true e junta os pedaços', async () => {
    sse.streamChat.mockImplementation(async function* () {
      yield { data: JSON.stringify({ choices: [{ delta: { role: 'assistant' } }] }) };
      yield { data: JSON.stringify({ choices: [{ delta: { content: 'Oi' } }] }) };
      yield { event: 'tool_call_start', data: '{}' };
      yield { data: JSON.stringify({ choices: [{ delta: { content: '!' } }] }) };
    });
    let texto = '';
    for await (const p of conversar([{ role: 'user', content: 'x' }], 'qwen3.5:4b')) texto += p;
    expect(texto).toBe('Oi!');
    const pedidoEnviado = sse.streamChat.mock.calls[0][0];
    expect(pedidoEnviado.editor).toBe(true);
    expect(pedidoEnviado.messages[0].role).toBe('system');
    expect(pedidoEnviado.model).toBe('qwen3.5:4b');
  });

  it('erro dentro do stream vira exceção', async () => {
    sse.streamChat.mockImplementation(async function* () {
      yield { data: JSON.stringify({ error: 'Ollama caiu' }) };
    });
    const gerador = conversar([{ role: 'user', content: 'x' }], 'm');
    await expect(gerador.next()).rejects.toThrow('Ollama caiu');
  });
});
