/** Brazilian Portuguese number and date formatting for the painel. */

const integer = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 });
const oneDecimal = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 });
const compact = new Intl.NumberFormat('pt-BR', { notation: 'compact', maximumFractionDigits: 1 });
const percent = new Intl.NumberFormat('pt-BR', { style: 'percent', maximumFractionDigits: 0 });

export const fmtInt = (n: number): string => integer.format(n);

/** 1.284 / 12,9 mil / 4,2 mi — for tiles and axis ticks. */
export const fmtCompact = (n: number): string => (Math.abs(n) < 1000 ? fmtSmall(n) : compact.format(n));

/** Small numbers keep one decimal (averages such as 2,4 instalações/dia). */
export const fmtSmall = (n: number): string =>
  Number.isInteger(n) ? integer.format(n) : oneDecimal.format(n);

export const fmtPercent = (ratio: number): string => percent.format(ratio);

const dayShort = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', timeZone: 'UTC' });
const dayLong = new Intl.DateTimeFormat('pt-BR', {
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  timeZone: 'UTC',
});
const dateTime = new Intl.DateTimeFormat('pt-BR', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  timeZone: 'America/Sao_Paulo',
});
const clock = new Intl.DateTimeFormat('pt-BR', {
  hour: '2-digit',
  minute: '2-digit',
  timeZone: 'America/Sao_Paulo',
});

const asDay = (day: string) => new Date(`${day}T12:00:00Z`);

/** "23/10" (the day is already a São Paulo calendar date). */
export const fmtDayShort = (day: unknown): string =>
  typeof day === 'string' && day ? dayShort.format(asDay(day)) : '';

/** "qui., 23 de out." */
export const fmtDayLong = (day: unknown): string =>
  typeof day === 'string' && day ? dayLong.format(asDay(day)) : '';

/** "23/10/2026, 14:05" in São Paulo time. */
export const fmtDateTime = (iso: string | null | undefined): string => {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '—' : dateTime.format(d);
};

export const fmtClock = (d: Date): string => clock.format(d);

/** Compact one-line rendering of an event's properties. */
export function fmtProperties(properties: Record<string, unknown>): string {
  const entries = Object.entries(properties);
  if (entries.length === 0) return '—';
  return entries
    .map(([key, value]) => {
      const text =
        typeof value === 'number'
          ? fmtSmall(value)
          : typeof value === 'boolean'
            ? value
              ? 'sim'
              : 'não'
            : typeof value === 'string'
              ? value
              : JSON.stringify(value);
      return `${key}: ${text}`;
    })
    .join(' · ');
}
