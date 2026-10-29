import { describe, expect, it } from 'vitest';
import { SentenceSplitter, splitSentences } from './sentence-splitter';

/** Feed `text` one character at a time, as a slow stream would. */
function streamed(text: string): { live: string[]; rest: string[] } {
  const splitter = new SentenceSplitter();
  const live: string[] = [];
  for (let i = 1; i <= text.length; i++) live.push(...splitter.update(text.slice(0, i)));
  return { live, rest: splitter.finish(text) };
}

describe('splitSentences', () => {
  it('cuts at . ! ? … and :', () => {
    expect(
      splitSentences(
        'Bom dia, tudo certo por aqui. Você viu a notícia de hoje? Que coisa mais incrível! '
          + 'Fiquei pensando nisso a noite toda… Resumo de toda a história: ninguém esperava.',
      ),
    ).toEqual([
      'Bom dia, tudo certo por aqui.',
      'Você viu a notícia de hoje?',
      'Que coisa mais incrível!',
      'Fiquei pensando nisso a noite toda…',
      'Resumo de toda a história:',
      'ninguém esperava.',
    ]);
  });

  it('does not cut after abbreviations, initials, numbers or URLs', () => {
    const text =
      'O Sr. Silva e a Dra. Ana chegaram às 15:30 com a versão 3.5 do app. '
      + 'Veja em https://exemplo.com.br/a.b?x=1 por ex. a página inicial. '
      + 'Quem escreveu foi J. R. Souza, com 2.500 páginas.';
    expect(splitSentences(text)).toEqual([
      'O Sr. Silva e a Dra. Ana chegaram às 15:30 com a versão 3.5 do app.',
      'Veja em https://exemplo.com.br/a.b?x=1 por ex. a página inicial.',
      'Quem escreveu foi J. R. Souza, com 2.500 páginas.',
    ]);
  });

  it('cuts at line breaks but keeps numbered list markers', () => {
    expect(
      splitSentences('Passos para instalar o programa\n1. Baixe o arquivo do site\n2. Abra o instalador agora'),
    ).toEqual([
      'Passos para instalar o programa',
      '1. Baixe o arquivo do site',
      '2. Abra o instalador agora',
    ]);
  });

  it('joins a short sentence with the next one', () => {
    expect(splitSentences('Claro! Vou te explicar como funciona isso.')).toEqual([
      'Claro! Vou te explicar como funciona isso.',
    ]);
    // ...but a short last sentence is still said.
    expect(splitSentences('Isso é tudo o que eu sei sobre o tema. Tchau!')).toEqual([
      'Isso é tudo o que eu sei sobre o tema.',
      'Tchau!',
    ]);
  });

  it('keeps a fenced code block in one piece and ignores dots inside inline code', () => {
    const text =
      'Use o comando `nicx ask. ok` no terminal agora.\n```bash\nnicx ask "Oi. Tudo bem?"\necho fim.\n```\nDepois veja o resultado na tela.';
    expect(splitSentences(text)).toEqual([
      'Use o comando `nicx ask. ok` no terminal agora.',
      '```bash\nnicx ask "Oi. Tudo bem?"\necho fim.\n```',
      'Depois veja o resultado na tela.',
    ]);
  });

  it('treats markdown emphasis after the punctuation as part of the sentence', () => {
    expect(splitSentences('**Atenção, isso é importante:** faça backup antes de tudo.')).toEqual([
      '**Atenção, isso é importante:**',
      'faça backup antes de tudo.',
    ]);
  });

  it('never speaks reasoning blocks', () => {
    expect(splitSentences('<think>Hmm. Vou pensar.</think>A resposta certa é quarenta e dois.')).toEqual([
      'A resposta certa é quarenta e dois.',
    ]);
  });

  it('cuts a very long sentence at a comma', () => {
    const long = `${'palavra '.repeat(20)}, ${'outra '.repeat(30)}, e mais ${'coisa '.repeat(5)}`;
    const splitter = new SentenceSplitter();
    const live = splitter.update(long);
    expect(live.length).toBeGreaterThan(0);
    expect(live.every((s) => s.endsWith(','))).toBe(true);
  });
});

describe('SentenceSplitter while streaming', () => {
  it('hands out each sentence as soon as it is complete, and the same ones as at the end', () => {
    const text = 'Primeiro, a previsão do tempo. Amanhã chove 3.5 mm em São Paulo! E depois esfria';
    const { live, rest } = streamed(text);
    expect(live).toEqual(['Primeiro, a previsão do tempo.', 'Amanhã chove 3.5 mm em São Paulo!']);
    expect(rest).toEqual(['E depois esfria']);
    expect([...live, ...rest]).toEqual(splitSentences(text));
  });

  it('waits to see what follows a dot before cutting', () => {
    const splitter = new SentenceSplitter();
    expect(splitter.update('A versão nova do Nicx é a 3.')).toEqual([]);
    expect(splitter.update('A versão nova do Nicx é a 3.5 e')).toEqual([]);
    expect(splitter.update('A versão nova do Nicx é a 3.5 e chegou. ')).toEqual([
      'A versão nova do Nicx é a 3.5 e chegou.',
    ]);
  });

  it('holds back an unfinished reasoning block or code fence', () => {
    const splitter = new SentenceSplitter();
    expect(splitter.update('<think>Primeiro passo. Segundo passo. ')).toEqual([]);
    expect(splitter.update('<think>Primeiro passo. Segundo passo.</think>Pronto, aqui está a resposta. ')).toEqual([
      'Pronto, aqui está a resposta.',
    ]);

    const code = new SentenceSplitter();
    expect(code.update('Veja este exemplo de código:\n```\nprint("um. dois. ')).toEqual([
      'Veja este exemplo de código:',
    ]);
    expect(code.update('Veja este exemplo de código:\n```\nprint("um. dois.")\n```\n')).toEqual([
      '```\nprint("um. dois.")\n```',
    ]);
  });

  it('never repeats a sentence across updates', () => {
    const text = 'Uma frase bem completa aqui. Outra frase bem completa ali. Mais uma para fechar.';
    const { live, rest } = streamed(text);
    const all = [...live, ...rest];
    expect(new Set(all).size).toBe(all.length);
    expect(all).toHaveLength(3);
  });
});
