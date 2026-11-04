import type { ReactNode } from 'react';

export const card = {
  background: 'var(--color-bg-secondary)',
  border: '1px solid var(--color-border)',
} as const;
export const input = {
  background: 'var(--color-bg)',
  border: '1px solid var(--color-border)',
  color: 'var(--color-text)',
} as const;
export const buttonClass =
  'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-default';
export const secondaryButton = {
  background: 'var(--color-bg-secondary)',
  color: 'var(--color-text-secondary)',
  border: '1px solid var(--color-border)',
} as const;
export const primaryButton = { background: 'var(--color-accent)', color: 'white', border: '1px solid transparent' } as const;
export const dangerButton = { ...secondaryButton, color: 'var(--color-error)', borderColor: 'var(--color-error)' } as const;
export const field = 'mt-1 w-full px-3 py-1.5 rounded-lg text-sm';
export const labelClass = 'block text-xs';

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'ok' | 'warn' | 'error' }) {
  const color =
    tone === 'ok'
      ? 'var(--color-success)'
      : tone === 'warn'
        ? 'var(--color-warning)'
        : tone === 'error'
          ? 'var(--color-error)'
          : 'var(--color-text-tertiary)';
  return (
    <span className="text-[10px] px-1.5 py-0.5 rounded shrink-0" style={{ border: `1px solid ${tone === 'neutral' ? 'var(--color-border)' : color}`, color }}>
      {children}
    </span>
  );
}

export function Message({ error, notice }: { error?: string; notice?: string }) {
  return (
    <>
      {notice && (
        <div className="text-xs mb-3" role="status" style={{ color: 'var(--color-success)' }}>
          {notice}
        </div>
      )}
      {error && (
        <div className="text-xs mb-3 whitespace-pre-line" role="alert" style={{ color: 'var(--color-error)' }}>
          {error}
        </div>
      )}
    </>
  );
}

export function errorText(e: unknown, fallback: string): string {
  return e instanceof Error ? e.message : fallback;
}
