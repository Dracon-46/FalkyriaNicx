import { describe, expect, it } from 'vitest';
import i18n, { LANGUAGES, detectLanguage, directionOf, setLanguage } from './index';

describe('idiomas', () => {
  it('português vem carregado e é o padrão', () => {
    expect(i18n.t('settings.language.label')).toBe('Idioma');
  });

  it('carrega outro idioma sob demanda (árabe da direita para a esquerda)', async () => {
    await setLanguage('ar');
    expect(i18n.t('settings.language.label')).toBe('اللغة');
    expect(directionOf(i18n.language)).toBe('rtl');
    await setLanguage('pt-BR');
    expect(directionOf(i18n.language)).toBe('ltr');
  });

  it('todo idioma tem os mesmos arquivos e chaves do português', async () => {
    const keys = (obj: unknown, prefix = ''): string[] =>
      typeof obj === 'object' && obj !== null
        ? Object.entries(obj).flatMap(([k, v]) => keys(v, `${prefix}${k}.`))
        : [prefix.slice(0, -1)];
    const base = keys(i18n.getResourceBundle('pt-BR', 'translation')).sort();
    for (const { code } of LANGUAGES.filter((l) => l.code !== 'pt-BR')) {
      await setLanguage(code);
      expect(keys(i18n.getResourceBundle(code, 'translation')).sort(), code).toEqual(base);
    }
    await setLanguage('pt-BR');
  });

  it('idioma desconhecido cai no português', async () => {
    await setLanguage('xx');
    expect(i18n.language).toBe('pt-BR');
    expect(['pt-BR', 'en', 'es', 'zh', 'hi', 'ar', 'fr']).toContain(detectLanguage());
  });
});
