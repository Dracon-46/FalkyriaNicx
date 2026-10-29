import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  fetchCalendarConfig,
  updateCalendarConfig,
  CalendarUnsupportedError,
  type CalendarConfig,
  type CalendarTarget,
} from '../../lib/api';

const TARGETS: CalendarTarget[] = ['windows', 'google', 'outlook', 'outlook_trabalho'];

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

/** Chave do texto (settings.calendar.accounts.*) para o estado de uma conta. */
function accountKey(connected: boolean, write: boolean | null): string {
  if (!connected) return 'none';
  if (write === null) return 'unknown';
  return write ? 'write' : 'readOnly';
}

/** Para onde "manda pro calendário" leva os compromissos (`[agenda]`). */
export function CalendarSettings({ onSaved }: { onSaved: () => void }) {
  const { t } = useTranslation();
  const [config, setConfig] = useState<CalendarConfig | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchCalendarConfig()
      .then((c) => {
        if (!cancelled) setConfig(c);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e instanceof CalendarUnsupportedError ? e.message : t('settings.calendar.serverUnavailable'));
      });
    return () => {
      cancelled = true;
    };
  }, [t]);

  const change = async (target: CalendarTarget) => {
    setSaving(true);
    setError('');
    try {
      setConfig(await updateCalendarConfig(target));
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('settings.calendar.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <Row label={t('settings.calendar.defaultLabel')} description={t('settings.calendar.defaultDescription')}>
        <select
          value={config?.calendario_padrao ?? 'windows'}
          disabled={!config || saving}
          aria-label={t('settings.calendar.defaultLabel')}
          onChange={(e) => void change(e.target.value as CalendarTarget)}
          className="px-2 py-1 rounded text-xs"
          style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
          data-testid="calendar-default"
        >
          {TARGETS.map((target) => (
            <option key={target} value={target}>
              {t(`settings.calendar.options.${target}`)}
            </option>
          ))}
        </select>
      </Row>
      <Row
        label={t('settings.calendar.accountsLabel')}
        description={
          config
            ? [
                t(`settings.calendar.accounts.google.${accountKey(config.google_conectado, config.google_escrita)}`),
                t(`settings.calendar.accounts.outlook.${accountKey(config.outlook_conectado, config.outlook_escrita)}`),
              ].join(' ')
            : error || t('settings.calendar.checking')
        }
      />
      <div className="text-xs mt-2 px-1" style={{ color: 'var(--color-text-tertiary)' }}>
        {t('settings.calendar.linkHint')}
      </div>
      {error && config && (
        <div className="text-xs mt-2 px-1" style={{ color: 'var(--color-error, #d33)' }}>
          {error}
        </div>
      )}
    </>
  );
}
