/**
 * The floating mascot window (`/flutuante`), opened by "Nicx, ligar".
 *
 * In the desktop window (pywebview) the page talks to its host through
 * `window.pywebview.api`; opened in a normal browser tab it falls back to
 * `window.close()`, which browsers only honour for windows a script opened.
 */

const FAREWELL_WORDS = new Set([
  'tchau', 'xau', 'adeus', 'desligar', 'desliga', 'desligue', 'dormir', 'dorme', 'durma',
  'encerrar', 'encerra', 'encerre', 'fechar', 'fecha', 'feche', 'sair',
]);
const FAREWELL_PAIRS = ['ate mais', 'ate logo', 'ate depois', 'boa noite', 'pode ir', 'pode parar'];
// Words that may surround a goodbye without making it a request.
const FILLERS = new Set([
  'nicx', 'nix', 'nics', 'nick', 'niks', 'ei', 'oi', 'ok', 'okay', 'pode', 'ja', 'agora', 'entao',
  'obrigado', 'obrigada', 'brigado', 'valeu', 'por', 'favor', 'e', 'pra', 'voce', 'se', 'a', 'o',
]);

export function normalizeWords(text: string): string[] {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .split(/[^a-z0-9]+/)
    .filter(Boolean);
}

/**
 * "Nicx, tchau", "pode desligar", "valeu, até mais": the user is done.
 * A question that merely mentions a farewell word ("como desligar o PC?")
 * is not a goodbye: everything besides the goodbye must be filler.
 */
export function isFarewell(text: string): boolean {
  let joined = ` ${normalizeWords(text).join(' ')} `;
  let found = false;
  for (const pair of FAREWELL_PAIRS) {
    if (joined.includes(` ${pair} `)) {
      found = true;
      joined = joined.split(` ${pair} `).join(' ');
    }
  }
  const rest = joined.split(' ').filter(Boolean);
  for (const word of rest) {
    if (FAREWELL_WORDS.has(word)) found = true;
    else if (!FILLERS.has(word)) return false;
  }
  return found;
}

interface PywebviewApi {
  fechar?: () => Promise<void> | void;
  pronto?: () => Promise<void> | void;
  problema?: (message: string) => Promise<void> | void;
}

function hostApi(): Promise<PywebviewApi | null> {
  const w = window as typeof window & { pywebview?: { api?: PywebviewApi } };
  if (w.pywebview?.api) return Promise.resolve(w.pywebview.api);
  return new Promise((resolve) => {
    const timer = setTimeout(() => resolve(null), 1500);
    window.addEventListener(
      'pywebviewready',
      () => {
        clearTimeout(timer);
        resolve(w.pywebview?.api ?? null);
      },
      { once: true },
    );
  });
}

/** True inside the desktop floating window (as opposed to a browser tab). */
export function inFloatingHost(): boolean {
  return Boolean((window as typeof window & { pywebview?: unknown }).pywebview);
}

/** Tell the host the mascot is listening (it logs the wake latency). */
export async function notifyFloatingReady(): Promise<void> {
  try {
    await (await hostApi())?.pronto?.();
  } catch {
    // Only a log line depends on it.
  }
}

/** Report a problem (no microphone...) to the host's log. */
export async function notifyFloatingProblem(message: string): Promise<void> {
  try {
    await (await hostApi())?.problema?.(message);
  } catch {
    // Only a log line depends on it.
  }
}

/** Close the floating window; false when the page is a normal browser tab. */
export async function closeFloatingWindow(): Promise<boolean> {
  try {
    const api = await hostApi();
    if (api?.fechar) {
      await api.fechar();
      return true;
    }
  } catch {
    // Fall through to window.close().
  }
  window.close();
  return window.closed;
}
