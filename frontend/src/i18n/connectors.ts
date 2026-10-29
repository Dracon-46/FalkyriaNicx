/**
 * Textos do catálogo de fontes (SOURCE_CATALOG) no idioma da interface.
 *
 * O catálogo continua em inglês, como dado. O que aparece na tela vem de
 * locales/<idioma>/connectors.json, com o inglês do catálogo como reserva:
 *
 *   connectors.<id>.description
 *   connectors.<id>.steps.<n>            (rótulo do passo; <n> começa em 1)
 *   connectors.<id>.links.<n>            (texto do link do passo <n>)
 *   connectors.<id>.troubleshooting.<n>
 *   connectors.<id>.fields.<campo>       (placeholder do campo)
 *   connectors.<id>.options.<valor>      (opções de campos do tipo select)
 *
 * O nome da fonte (display_name) é marca e não muda. Chame durante a
 * renderização de um componente com useTranslation(), para que a troca de
 * idioma redesenhe a tela.
 */
import i18n from './index';
import type { ConnectorMeta } from '../types/connectors';

function tr(key: string, fallback: string): string {
  return i18n.t(`connectors.${key}`, { defaultValue: fallback });
}

/** Cópia do item do catálogo com os textos visíveis no idioma atual. */
export function localizeConnector(meta: ConnectorMeta): ConnectorMeta;
export function localizeConnector(meta: ConnectorMeta | null | undefined): ConnectorMeta | undefined;
export function localizeConnector(meta: ConnectorMeta | null | undefined): ConnectorMeta | undefined {
  if (!meta) return undefined;
  const id = meta.connector_id;
  return {
    ...meta,
    description: tr(`${id}.description`, meta.description),
    steps: meta.steps?.map((step, i) => ({
      ...step,
      label: tr(`${id}.steps.${i + 1}`, step.label),
      urlLabel: step.urlLabel ? tr(`${id}.links.${i + 1}`, step.urlLabel) : step.urlLabel,
    })),
    troubleshooting: meta.troubleshooting?.map((tip, i) => tr(`${id}.troubleshooting.${i + 1}`, tip)),
    inputFields: meta.inputFields?.map((field) => ({
      ...field,
      placeholder: tr(`${id}.fields.${field.name}`, field.placeholder),
      options: field.options?.map((option) => ({
        ...option,
        label: tr(`${id}.options.${option.value}`, option.label),
      })),
    })),
  };
}

/** Unidades do catálogo (em inglês, `unitLabel`) -> chave em dataSources.units. */
const UNIT_KEYS: Record<string, string> = {
  items: 'items',
  documents: 'documents',
  emails: 'emails',
  messages: 'messages',
  pages: 'pages',
  'meeting notes': 'meetingNotes',
  notes: 'notes',
  files: 'files',
  events: 'events',
  contacts: 'contacts',
};

/** Unidade de contagem de uma fonte ("emails" -> "e-mails") no idioma atual. */
export function unitText(unit: string): string {
  const key = UNIT_KEYS[unit];
  return key ? i18n.t(`dataSources.units.${key}`) : unit;
}
