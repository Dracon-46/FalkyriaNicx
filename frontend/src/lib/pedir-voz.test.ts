import { describe, expect, it } from 'vitest';
import { pedeVoz } from './pedir-voz';

describe('pedeVoz: o Nicx fala só quando pedem', () => {
  it.each([
    'responde falando',
    'me explica isso falando',
    'lê em voz alta pra mim',
    'lê isso pra mim',
    'Qual a previsão do tempo? Responde com sua voz',
    'fala isso alto',
    'read it aloud',
    'say it out loud please',
    'léelo en voz alta',
  ])('pede: %s', (frase) => {
    expect(pedeVoz(frase)).toBe(true);
  });

  it.each([
    'me fala sobre a fotossíntese',
    'fala comigo sobre o projeto',
    'aumenta o volume',
    'escreve um texto falando de futebol',
    'como eu falo em público?',
    'what does aloe vera do',
  ])('não pede: %s', (frase) => {
    expect(pedeVoz(frase)).toBe(false);
  });
});
