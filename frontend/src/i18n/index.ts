/**
 * Idiomas da interface do Nicx.
 *
 * Os textos ficam em ./locales/<idioma>/<área>.json (uma área por parte do
 * app: settings, chat, sidebar...). Cada arquivo vira a chave da área:
 * locales/en/chat.json -> t('chat.send'). Português é o padrão e vem junto
 * com o app; os outros idiomas carregam sob demanda. O mesmo idioma vale
 * para as respostas do Nicx e para a voz.
 */
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

export interface Language {
  code: string;
  /** Nome no próprio idioma, como aparece no seletor. */
  name: string;
  dir: 'ltr' | 'rtl';
}

export const DEFAULT_LANGUAGE = 'pt-BR';

export const LANGUAGES: Language[] = [
  { code: 'pt-BR', name: 'Português (Brasil)', dir: 'ltr' },
  { code: 'en', name: 'English', dir: 'ltr' },
  { code: 'es', name: 'Español', dir: 'ltr' },
  { code: 'zh', name: '中文（简体）', dir: 'ltr' },
  { code: 'hi', name: 'हिन्दी', dir: 'ltr' },
  { code: 'ar', name: 'العربية', dir: 'rtl' },
  { code: 'fr', name: 'Français', dir: 'ltr' },
];

type Bundle = Record<string, unknown>;

const defaultFiles = import.meta.glob<Bundle>('./locales/pt-BR/*.json', {
  eager: true,
  import: 'default',
});
const otherFiles = import.meta.glob<Bundle>(['./locales/*/*.json', '!./locales/pt-BR/*.json'], {
  import: 'default',
});

/** './locales/en/chat.json' -> ['en', 'chat'] */
function parts(path: string): [string, string] {
  const [, code, file] = path.match(/\.\/locales\/([^/]+)\/([^/]+)\.json$/) ?? [];
  return [code ?? '', file ?? ''];
}

function bundleOf(files: Record<string, Bundle>): Bundle {
  const bundle: Bundle = {};
  for (const [path, content] of Object.entries(files)) bundle[parts(path)[1]] = content;
  return bundle;
}

async function loadLanguage(code: string): Promise<Bundle> {
  const entries = Object.entries(otherFiles).filter(([path]) => parts(path)[0] === code);
  const loaded = await Promise.all(entries.map(async ([path, load]) => [path, await load()] as const));
  return bundleOf(Object.fromEntries(loaded));
}

export function directionOf(code: string): 'ltr' | 'rtl' {
  return LANGUAGES.find((l) => l.code === code)?.dir ?? 'ltr';
}

export function isSupported(code: string): boolean {
  return LANGUAGES.some((l) => l.code === code);
}

/** Primeiro acesso: o idioma do sistema, se o Nicx o tiver; senão, português. */
export function detectLanguage(): string {
  const candidates = typeof navigator !== 'undefined' ? navigator.languages ?? [navigator.language] : [];
  for (const raw of candidates) {
    if (!raw) continue;
    if (isSupported(raw)) return raw;
    const base = raw.split('-')[0];
    if (base === 'pt') return 'pt-BR';
    if (isSupported(base)) return base;
  }
  return DEFAULT_LANGUAGE;
}

function applyDocument(code: string) {
  if (typeof document === 'undefined') return;
  document.documentElement.lang = code;
  document.documentElement.dir = directionOf(code);
}

/** Troca o idioma da interface (carrega os arquivos do idioma se preciso). */
export async function setLanguage(code: string): Promise<void> {
  const target = isSupported(code) ? code : DEFAULT_LANGUAGE;
  if (target !== DEFAULT_LANGUAGE && !i18n.hasResourceBundle(target, 'translation')) {
    i18n.addResourceBundle(target, 'translation', await loadLanguage(target), true, true);
  }
  await i18n.changeLanguage(target);
  applyDocument(target);
}

void i18n.use(initReactI18next).init({
  resources: { [DEFAULT_LANGUAGE]: { translation: bundleOf(defaultFiles) } },
  lng: DEFAULT_LANGUAGE,
  fallbackLng: DEFAULT_LANGUAGE,
  interpolation: { escapeValue: false },
  returnNull: false,
});

export default i18n;
