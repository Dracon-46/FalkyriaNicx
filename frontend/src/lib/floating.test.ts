import { describe, expect, it } from 'vitest';
import { isFarewell, normalizeWords } from './floating';

describe('isFarewell', () => {
  it.each([
    'Nicx, tchau',
    'tchau',
    'Tchau!',
    'Pode desligar.',
    'desliga',
    'Nicx, desligar',
    'Valeu, até mais!',
    'Obrigado, Nicx. Até logo.',
    'Ok, pode ir',
    'Boa noite, Nicx',
  ])('recognizes "%s" as a goodbye', (text) => {
    expect(isFarewell(text)).toBe(true);
  });

  it.each([
    'Como desligar o computador?',
    'Me explica o que significa tchau em italiano',
    'Que horas são?',
    'Nicx',
    '',
    'Até mais tarde eu quero falar sobre o relatório',
    'Pode ligar a luz?',
  ])('does not treat "%s" as a goodbye', (text) => {
    expect(isFarewell(text)).toBe(false);
  });
});

describe('normalizeWords', () => {
  it('drops accents and punctuation', () => {
    expect(normalizeWords('Até logo, Nicx!')).toEqual(['ate', 'logo', 'nicx']);
  });
});
