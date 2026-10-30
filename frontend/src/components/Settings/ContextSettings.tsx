import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  fetchScreenContextConfig,
  updateScreenContextConfig,
  type ScreenContextConfig,
  type ScreenContextUpdate,
} from '../../lib/api';

function Row({ label, description, children }: { label: string; description?: string; children?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 py-3" style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
      <div className="min-w-0">
        <div className="text-sm" style={{ color: 'var(--color-text)' }}>{label}</div>
        {description && (
          <div className="text-xs mt-0.5 break-words" style={{ color: 'var(--color-text-tertiary)' }}>{description}</div>
        )}
      </div>
      {children && <div className="shrink-0">{children}</div>}
    </div>
  );
}

function Switch({
  on,
  disabled,
  label,
  onClick,
  testId,
}: {
  on: boolean;
  disabled: boolean;
  label: string;
  onClick: () => void;
  testId: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
      data-testid={testId}
      className="relative w-11 h-6 rounded-full transition-colors cursor-pointer disabled:cursor-default"
      style={{ background: on ? 'var(--color-accent)' : 'var(--color-bg-tertiary)', opacity: disabled ? 0.4 : 1 }}
    >
      <span
        className="absolute top-0.5 left-0.5 w-5 h-5 rounded-full transition-transform bg-white"
        style={{ transform: on ? 'translateX(20px)' : 'translateX(0)', boxShadow: '0 1px 3px rgba(0,0,0,0.2)' }}
      />
    </button>
  );
}

/** "Resume o que eu copiei", "explica isso aqui" (`[contexto]`). */
export function ContextSettings({ onSaved }: { onSaved: () => void }) {
  const { t, i18n } = useTranslation();
  const [config, setConfig] = useState<ScreenContextConfig | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchScreenContextConfig()
      .then((c) => {
        if (!cancelled) setConfig(c);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : t('settings.context.serverUnavailable'));
      });
    return () => {
      cancelled = true;
    };
  }, [t]);

  const change = async (update: ScreenContextUpdate) => {
    setSaving(true);
    setError('');
    try {
      setConfig(await updateScreenContextConfig(update));
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('settings.context.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  const busy = !config || saving;
  const limits = config?.limites?.length ? config.limites : [5000, 10000, 20000, 40000];
  const current = config?.max_caracteres ?? 20000;
  const options = limits.includes(current) ? limits : [...limits, current].sort((a, b) => a - b);
  const number = new Intl.NumberFormat(i18n.language);

  return (
    <>
      <Row label={t('settings.context.enabledLabel')} description={t('settings.context.enabledDescription')}>
        <Switch
          on={config?.ativo ?? false}
          disabled={busy}
          label={t('settings.context.enabledLabel')}
          onClick={() => void change({ ativo: !config?.ativo })}
          testId="context-enabled"
        />
      </Row>
      <Row label={t('settings.context.copyLabel')} description={t('settings.context.copyDescription')}>
        <Switch
          on={config?.copiar_selecao ?? false}
          disabled={busy || !config?.ativo}
          label={t('settings.context.copyLabel')}
          onClick={() => void change({ copiar_selecao: !config?.copiar_selecao })}
          testId="context-copy"
        />
      </Row>
      <Row label={t('settings.context.limitLabel')} description={t('settings.context.limitDescription')}>
        <select
          value={current}
          disabled={busy || !config?.ativo}
          aria-label={t('settings.context.limitLabel')}
          onChange={(e) => void change({ max_caracteres: Number(e.target.value) })}
          className="px-2 py-1 rounded text-xs"
          style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
          data-testid="context-limit"
        >
          {options.map((value) => (
            <option key={value} value={value}>
              {t('settings.context.limitOption', { formatted: number.format(value) })}
            </option>
          ))}
        </select>
      </Row>
      <div className="text-xs mt-2 px-1" style={{ color: 'var(--color-text-tertiary)' }}>
        {config && !config.suportado ? t('settings.context.windowsOnly') : t('settings.context.privacyHint')}
      </div>
      {error && (
        <div className="text-xs mt-2 px-1" style={{ color: 'var(--color-error, #d33)' }}>
          {error}
        </div>
      )}
    </>
  );
}
