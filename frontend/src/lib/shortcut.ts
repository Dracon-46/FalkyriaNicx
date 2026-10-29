/**
 * Atalho global de teclado: transforma as teclas apertadas no formato que o
 * servidor grava em `[atalho] teclas` ("ctrl+alt+n") e o mostra como
 * "Ctrl + Alt + N". O servidor valida de novo (src/nicx/atalho/teclas.py);
 * aqui a checagem existe só para avisar na hora, no idioma da interface.
 */

/** Ordem canônica, igual à do servidor. */
export const MODIFIERS = ['ctrl', 'alt', 'shift', 'win'] as const;
export type Modifier = (typeof MODIFIERS)[number];

const MODIFIER_LABELS: Record<Modifier, string> = { ctrl: 'Ctrl', alt: 'Alt', shift: 'Shift', win: 'Win' };

const SPECIAL_CODES: Record<string, string> = {
  Space: 'space',
  Enter: 'enter',
  NumpadEnter: 'enter',
  Tab: 'tab',
  Escape: 'escape',
  Backspace: 'backspace',
  Insert: 'insert',
  Delete: 'delete',
  Home: 'home',
  End: 'end',
  PageUp: 'pageup',
  PageDown: 'pagedown',
  ArrowUp: 'up',
  ArrowDown: 'down',
  ArrowLeft: 'left',
  ArrowRight: 'right',
  Pause: 'pause',
};

const KEY_LABELS: Record<string, string> = {
  space: 'Space',
  enter: 'Enter',
  tab: 'Tab',
  escape: 'Esc',
  backspace: 'Backspace',
  insert: 'Insert',
  delete: 'Delete',
  home: 'Home',
  end: 'End',
  pageup: 'PageUp',
  pagedown: 'PageDown',
  up: '↑',
  down: '↓',
  left: '←',
  right: '→',
  pause: 'Pause',
};

const MODIFIER_CODES = new Set([
  'ControlLeft', 'ControlRight', 'AltLeft', 'AltRight', 'ShiftLeft', 'ShiftRight',
  'MetaLeft', 'MetaRight', 'OSLeft', 'OSRight',
]);

/** Combinações do Windows ou de uso geral (mesma lista do servidor). */
export const RESERVED_COMBOS: ReadonlySet<string> = new Set([
  'ctrl+alt+delete', 'ctrl+shift+escape', 'ctrl+escape', 'alt+tab', 'alt+shift+tab',
  'ctrl+alt+tab', 'alt+escape', 'alt+f4', 'alt+space', 'ctrl+alt+backspace',
  'ctrl+a', 'ctrl+c', 'ctrl+v', 'ctrl+x', 'ctrl+z', 'ctrl+y', 'ctrl+s', 'ctrl+f',
  'ctrl+p', 'ctrl+w', 'ctrl+t', 'ctrl+n', 'ctrl+o', 'ctrl+shift+z', 'ctrl+shift+t',
  'ctrl+shift+n', 'ctrl+tab', 'ctrl+shift+tab', 'ctrl+f4',
  ...'l d e r i a s v p g h k m u x b c n o q t w z tab space up down left right home pause enter escape 1 2 3 4 5 6 7 8 9 0'
    .split(' ')
    .map((key) => `win+${key}`),
  'ctrl+win+d', 'ctrl+win+left', 'ctrl+win+right', 'ctrl+win+f4',
  'shift+win+s', 'shift+win+left', 'shift+win+right',
]);

export type ComboError = 'needModifier' | 'unsupportedKey' | 'reserved';

export type ComboResult =
  /** Só modificadores apertados até agora. */
  | { kind: 'pending'; modifiers: Modifier[] }
  /** Esc sozinho: desistiu de gravar. */
  | { kind: 'cancel' }
  | { kind: 'done'; combo: string }
  | { kind: 'error'; reason: ComboError; combo?: string };

export interface KeyLike {
  code: string;
  ctrlKey: boolean;
  altKey: boolean;
  shiftKey: boolean;
  metaKey: boolean;
}

/** Tecla principal a partir do `code` (independe do layout do teclado). */
export function keyFromCode(code: string): string | null {
  let m = /^Key([A-Z])$/.exec(code);
  if (m) return m[1].toLowerCase();
  // Só a fileira de cima: o teclado numérico tem outros códigos no Windows.
  m = /^Digit([0-9])$/.exec(code);
  if (m) return m[1];
  m = /^F([0-9]{1,2})$/.exec(code);
  if (m && Number(m[1]) >= 1 && Number(m[1]) <= 24) return `f${m[1]}`;
  return SPECIAL_CODES[code] ?? null;
}

function modifiersOf(e: KeyLike): Modifier[] {
  const held: Record<Modifier, boolean> = { ctrl: e.ctrlKey, alt: e.altKey, shift: e.shiftKey, win: e.metaKey };
  return MODIFIERS.filter((mod) => held[mod]);
}

/** Lê um `keydown` enquanto o usuário grava a combinação. */
export function comboFromKeyEvent(e: KeyLike): ComboResult {
  const modifiers = modifiersOf(e);
  if (MODIFIER_CODES.has(e.code)) return { kind: 'pending', modifiers };
  if (e.code === 'Escape' && modifiers.length === 0) return { kind: 'cancel' };
  const key = keyFromCode(e.code);
  if (!key) return { kind: 'error', reason: 'unsupportedKey' };
  if (!modifiers.some((mod) => mod !== 'shift')) return { kind: 'error', reason: 'needModifier' };
  const combo = [...modifiers, key].join('+');
  if (RESERVED_COMBOS.has(combo)) return { kind: 'error', reason: 'reserved', combo };
  return { kind: 'done', combo };
}

/** "ctrl+alt+n" -> "Ctrl + Alt + N". `names` traduz teclas (ex.: space). */
export function formatCombo(combo: string, names: Partial<Record<string, string>> = {}): string {
  if (!combo) return '';
  return combo
    .split('+')
    .map((part) => {
      if (part in names && names[part]) return names[part] as string;
      if ((MODIFIERS as readonly string[]).includes(part)) return MODIFIER_LABELS[part as Modifier];
      return KEY_LABELS[part] ?? part.toUpperCase();
    })
    .join(' + ');
}

/** Rótulo parcial enquanto só os modificadores estão apertados: "Ctrl + Alt + …". */
export function formatPending(modifiers: Modifier[]): string {
  return modifiers.length ? `${modifiers.map((mod) => MODIFIER_LABELS[mod]).join(' + ')} + …` : '';
}
