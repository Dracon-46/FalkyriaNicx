import { describe, expect, it } from 'vitest';
import i18n, { setLanguage } from './index';
import { localizeConnector } from './connectors';
import { SOURCE_CATALOG } from '../types/connectors';

describe('textos do catálogo de fontes', () => {
  it('todo texto visível do catálogo tem tradução', () => {
    for (const meta of SOURCE_CATALOG) {
      const id = meta.connector_id;
      const keys = [
        `${id}.description`,
        ...(meta.steps ?? []).map((_, i) => `${id}.steps.${i + 1}`),
        ...(meta.steps ?? []).flatMap((s, i) => (s.urlLabel ? [`${id}.links.${i + 1}`] : [])),
        ...(meta.troubleshooting ?? []).map((_, i) => `${id}.troubleshooting.${i + 1}`),
        ...(meta.inputFields ?? []).flatMap((f) => (f.options ?? []).map((o) => `${id}.options.${o.value}`)),
      ];
      for (const key of keys) expect(i18n.exists(`connectors.${key}`), key).toBe(true);
    }
  });

  it('mostra em português e mantém os dados', () => {
    const gmail = SOURCE_CATALOG.find((s) => s.connector_id === 'gmail_imap')!;
    const pt = localizeConnector(gmail);
    expect(pt.description).toBe('E-mails e conversas');
    expect(pt.unitLabel).toBe(gmail.unitLabel);
    expect(pt.steps?.[0].url).toBe(gmail.steps?.[0].url);
    expect(pt.inputFields?.map((f) => f.name)).toEqual(['email', 'password']);
    expect(localizeConnector(undefined)).toBeUndefined();
  });

  it('em inglês fica igual ao catálogo', async () => {
    await setLanguage('en');
    for (const meta of SOURCE_CATALOG) expect(localizeConnector(meta), meta.connector_id).toEqual(meta);
    await setLanguage('pt-BR');
  });
});
