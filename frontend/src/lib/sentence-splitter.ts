/**
 * Cuts a reply into sentences while it is still being written, so voice
 * output can start on the first finished sentence instead of the whole text.
 *
 * Boundaries: `.`, `!`, `?`, `…` and `:` followed by whitespace, and line
 * breaks. Not boundaries: common abbreviations ("Sr.", "Dr.", "ex."), single
 * letters ("J. Silva"), numbers and URLs (the dot is not followed by a space),
 * list markers ("1. Item"), and anything inside inline code. A fenced code
 * block is one segment of its own and is held back until it closes. Segments
 * shorter than `minChars` are merged into the next one, so the voice never
 * stops after a lone "Claro!".
 *
 * `update()` takes the whole text received so far (not a delta) and returns
 * the sentences that became final; `finish()` returns what is left.
 */

/** Shortest segment spoken on its own; shorter ones join the next. */
export const MIN_SENTENCE_CHARS = 20;
/** A sentence longer than this without a full stop is cut at a comma. */
export const MAX_SENTENCE_CHARS = 220;

/** Lower-case words that end in a dot without ending the sentence. */
const ABBREVIATIONS = new Set([
  // pt-BR / es / fr / en titles
  'sr', 'sra', 'srta', 'srs', 'sras', 'dr', 'dra', 'drs', 'dras', 'prof', 'profa', 'profs',
  'eng', 'arq', 'adv', 'exmo', 'exma', 'ilmo', 'ilma', 'v.exa', 'mr', 'mrs', 'ms', 'st',
  'jr', 'mme', 'mlle', 'ud', 'uds', 'dña', 'sto', 'sta',
  // references and units (words that also end real sentences, like "mar" or
  // "no", are left out: a false merge only delays the voice a little)
  'ex', 'p.ex', 'e.g', 'i.e', 'vs', 'cf', 'obs', 'aprox', 'approx', 'pág', 'pag', 'págs', 'pp',
  'cap', 'arts', 'inc', 'vol', 'fig', 'nº', 'n°', 'núm', 'num', 'tel', 'av', 'ltda', 'cia',
  'corp', 'dept', 'depto', 'máx', 'mín', 'hr', 'hrs', 'qtd', 'qtde', 'etc',
  // months
  'jan', 'fev', 'feb', 'abr', 'apr', 'jun', 'jul', 'ago', 'aug', 'sep', 'oct', 'nov', 'dez',
  'dec',
]);

const TERMINATORS = '.!?…:';
/** Characters that may close a sentence after its punctuation ("ok.**", "(sim.)"). */
const CLOSERS = '*_`)]"\'”’»';

/** Remove reasoning blocks; hold back an unclosed one or a tag still arriving. */
function speechText(text: string, final: boolean): string {
  let t = text.replace(/<think>[\s\S]*?<\/think>\s*/gi, '');
  const open = t.search(/<think>/i);
  if (open >= 0) t = t.slice(0, open);
  // A closing tag with no opening one: everything before it was reasoning.
  const orphan = t.search(/<\/think>/i);
  if (orphan >= 0) t = t.slice(orphan + '</think>'.length).replace(/^\s+/, '');
  if (!final) {
    const tail = t.match(/<\/?[a-z]*$/i);
    if (tail && ('<think>'.startsWith(tail[0].toLowerCase()) || '</think>'.startsWith(tail[0].toLowerCase()))) {
      t = t.slice(0, tail.index);
    }
  }
  return t;
}

function isSpace(ch: string | undefined): boolean {
  return ch !== undefined && /\s/.test(ch);
}

/** The word right before position `dot`, without leading punctuation. */
function wordBefore(text: string, dot: number): string {
  let i = dot;
  while (i > 0 && !isSpace(text[i - 1])) i -= 1;
  return text.slice(i, dot).replace(/^[([{"'“‘«*_`]+/, '');
}

/** Is the dot at `dot` a list marker like "1." or "10." at the start of a line? */
function isListMarker(text: string, dot: number, lineStart: number): boolean {
  const before = text.slice(lineStart, dot);
  return /^\s*\d{1,3}$/.test(before);
}

function isAbbreviation(word: string): boolean {
  const w = word.toLowerCase();
  if (!w) return false;
  if (/^\p{L}$/u.test(w)) return true; // initials: "J. Silva"
  return ABBREVIATIONS.has(w);
}

export class SentenceSplitter {
  /** End of the text already handed out (or held in `carryStart..`). */
  private pos = 0;
  /** Start of a short segment waiting to be merged with the next one, or -1. */
  private carryStart = -1;
  private seen = '';
  private finished = false;

  constructor(
    private readonly minChars = MIN_SENTENCE_CHARS,
    private readonly maxChars = MAX_SENTENCE_CHARS,
  ) {}

  /** Feed the whole text received so far; returns the sentences now complete. */
  update(fullText: string): string[] {
    if (this.finished) return [];
    return this.scan(speechText(fullText, false), false);
  }

  /** The text is complete: return every remaining sentence. */
  finish(fullText?: string): string[] {
    if (this.finished) return [];
    const text = fullText === undefined ? this.seen : speechText(fullText, true);
    const out = this.scan(text, true);
    this.finished = true;
    return out;
  }

  private scan(text: string, final: boolean): string[] {
    // The cleaned text changed under us (a late </think> turned what we had
    // into reasoning): start over on the new text rather than skip the reply.
    if (!text.startsWith(this.seen.slice(0, this.pos))) {
      this.pos = 0;
      this.carryStart = -1;
    }
    this.seen = text;

    const out: string[] = [];
    const emit = (start: number, end: number) => {
      const from = this.carryStart >= 0 ? this.carryStart : start;
      const segment = text.slice(from, end).trim();
      this.pos = end;
      if (!segment) {
        this.carryStart = -1;
        return;
      }
      if (segment.length < this.minChars) {
        this.carryStart = from;
        return;
      }
      this.carryStart = -1;
      out.push(segment);
    };

    let start = this.pos;
    let lineStart = text.lastIndexOf('\n', start - 1) + 1;
    let inlineCode = false;
    let i = start;

    while (i < text.length) {
      const ch = text[i];

      // Fenced code block: one segment, only once it is closed.
      if (ch === '`' && text.startsWith('```', i) && /^\s*$/.test(text.slice(lineStart, i))) {
        const close = text.indexOf('```', i + 3);
        if (close < 0) {
          if (!final) return out;
          emit(start, i);
          emit(i, text.length);
          start = text.length;
          i = text.length;
          break;
        }
        if (text.slice(start, i).trim()) emit(start, i);
        const lineEnd = text.indexOf('\n', close + 3);
        const end = lineEnd < 0 ? text.length : lineEnd + 1;
        if (lineEnd < 0 && !final) return out; // the closing line may still grow
        emit(i, end);
        start = end;
        lineStart = end;
        i = end;
        inlineCode = false;
        continue;
      }

      if (ch === '`') {
        inlineCode = !inlineCode;
        i += 1;
        continue;
      }

      if (ch === '\n') {
        emit(start, i + 1);
        start = i + 1;
        lineStart = i + 1;
        inlineCode = false;
        i += 1;
        continue;
      }

      if (!inlineCode && TERMINATORS.includes(ch)) {
        let j = i;
        while (j < text.length && TERMINATORS.includes(text[j])) j += 1;
        while (j < text.length && CLOSERS.includes(text[j])) j += 1;
        if (j >= text.length) {
          // "3." may still become "3.5": decide when more text arrives.
          if (!final) break;
        } else if (!isSpace(text[j])) {
          i = j;
          continue;
        }
        const run = text.slice(i, j).replace(/[*_`)\]"'”’»]+$/, '');
        const singleDot = run === '.';
        if (
          singleDot
          && (isAbbreviation(wordBefore(text, i)) || isListMarker(text, i, lineStart))
        ) {
          i = j;
          continue;
        }
        emit(start, j);
        start = j;
        i = j;
        continue;
      }

      i += 1;
    }

    if (final) {
      if (start < text.length || this.carryStart >= 0) {
        const from = this.carryStart >= 0 ? this.carryStart : start;
        const rest = text.slice(from).trim();
        if (rest) out.push(rest);
      }
      this.carryStart = -1;
      this.pos = text.length;
      return out;
    }

    // A long sentence with no full stop yet: cut it at the last comma.
    const pendingFrom = this.carryStart >= 0 ? this.carryStart : start;
    const safeEnd = i; // never past a terminator still undecided
    if (safeEnd - pendingFrom > this.maxChars) {
      const window = text.slice(pendingFrom, safeEnd);
      const cut = Math.max(window.lastIndexOf(', '), window.lastIndexOf('; '));
      if (cut >= this.minChars && !/`/.test(window)) {
        emit(start, pendingFrom + cut + 1);
      }
    }
    return out;
  }
}

/** Split a finished text into speakable sentences. */
export function splitSentences(text: string): string[] {
  return new SentenceSplitter().finish(text);
}
