import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  DAILY_SUMMARY_DAYS,
  fetchDailySummary,
  fetchDailySummaryConfig,
  updateDailySummaryConfig,
  type DailySummary,
  type DailySummaryConfig,
  type DailySummaryDay,
  type DailySummaryUpdate,
} from '../../lib/resumo';

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

const buttonStyle = {
  background: 'var(--color-bg-secondary)',
  color: 'var(--color-text-secondary)',
  border: '1px solid var(--color-border)',
};

/** Resumo do dia: o texto de hoje e o resumo automático (`[resumo]`). */
export function DailySummarySettings({ onSaved }: { onSaved: () => void }) {
  const { t, i18n } = useTranslation();
  const [config, setConfig] = useState<DailySummaryConfig | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [summary, setSummary] = useState<DailySummary | null>(null);
  const [loading, setLoading] = useState<'' | 'plain' | 'refine'>('');
  const [summaryError, setSummaryError] = useState('');

  useEffect(() => {
    let cancelled = false;
    fetchDailySummaryConfig()
      .then((c) => {
        if (!cancelled) setConfig(c);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : t('settings.dailySummary.serverUnavailable'));
      });
    return () => {
      cancelled = true;
    };
  }, [t]);

  const change = async (update: DailySummaryUpdate) => {
    setSaving(true);
    setError('');
    try {
      setConfig(await updateDailySummaryConfig(update));
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('settings.dailySummary.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  const toggleDay = (day: DailySummaryDay) => {
    if (!config) return;
    const chosen = config.dias.includes(day) ? config.dias.filter((d) => d !== day) : [...config.dias, day];
    void change({ dias: DAILY_SUMMARY_DAYS.filter((d) => chosen.includes(d)) });
  };

  const show = async (refine: boolean) => {
    setLoading(refine ? 'refine' : 'plain');
    setSummaryError('');
    try {
      setSummary(await fetchDailySummary(i18n.language, refine));
    } catch (e) {
      setSummaryError(e instanceof Error ? e.message : t('settings.dailySummary.loadFailed'));
    } finally {
      setLoading('');
    }
  };

  const busy = !config || saving;
  const days = config?.opcoes_dias?.length ? config.opcoes_dias : DAILY_SUMMARY_DAYS;

  return (
    <>
      <Row label={t('settings.dailySummary.enabledLabel')} description={t('settings.dailySummary.enabledDescription')}>
        <Switch
          on={config?.ativo ?? false}
          disabled={busy}
          label={t('settings.dailySummary.enabledLabel')}
          onClick={() => void change({ ativo: !config?.ativo })}
          testId="summary-enabled"
        />
      </Row>
      <Row label={t('settings.dailySummary.timeLabel')} description={t('settings.dailySummary.timeDescription')}>
        <input
          type="time"
          value={config?.hora ?? '18:00'}
          disabled={busy}
          aria-label={t('settings.dailySummary.timeLabel')}
          onChange={(e) => {
            if (/^\d{2}:\d{2}$/.test(e.target.value)) void change({ hora: e.target.value });
          }}
          className="px-2 py-1 rounded text-xs"
          style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
          data-testid="summary-time"
        />
      </Row>
      <div className="py-3" style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
        <div className="text-sm" style={{ color: 'var(--color-text)' }}>{t('settings.dailySummary.daysLabel')}</div>
        <div className="text-xs mt-0.5" style={{ color: 'var(--color-text-tertiary)' }}>
          {t('settings.dailySummary.daysDescription')}
        </div>
        <div className="flex flex-wrap gap-1.5 mt-2" role="group" aria-label={t('settings.dailySummary.daysLabel')}>
          {days.map((day) => {
            const on = config?.dias.includes(day) ?? false;
            return (
              <button
                key={day}
                type="button"
                aria-pressed={on}
                disabled={busy}
                onClick={() => toggleDay(day)}
                data-testid={`summary-day-${day}`}
                className="px-2.5 py-1 rounded-full text-xs font-medium transition-colors cursor-pointer disabled:cursor-default"
                style={{
                  background: on ? 'var(--color-accent)' : 'var(--color-bg-secondary)',
                  color: on ? '#fff' : 'var(--color-text-secondary)',
                  border: '1px solid var(--color-border)',
                  opacity: busy ? 0.6 : 1,
                }}
              >
                {t(`settings.dailySummary.days.${day}`)}
              </button>
            );
          })}
        </div>
      </div>
      <Row label={t('settings.dailySummary.speakLabel')} description={t('settings.dailySummary.speakDescription')}>
        <Switch
          on={config?.falar ?? false}
          disabled={busy}
          label={t('settings.dailySummary.speakLabel')}
          onClick={() => void change({ falar: !config?.falar })}
          testId="summary-speak"
        />
      </Row>
      <Row label={t('settings.dailySummary.notifyLabel')} description={t('settings.dailySummary.notifyDescription')}>
        <Switch
          on={config?.notificar ?? false}
          disabled={busy}
          label={t('settings.dailySummary.notifyLabel')}
          onClick={() => void change({ notificar: !config?.notificar })}
          testId="summary-notify"
        />
      </Row>
      <div className="flex flex-wrap gap-2 mt-3">
        <button
          type="button"
          onClick={() => void show(false)}
          disabled={loading !== ''}
          data-testid="summary-show"
          className="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer disabled:cursor-default"
          style={buttonStyle}
        >
          {loading === 'plain' ? t('settings.dailySummary.loading') : t('settings.dailySummary.showToday')}
        </button>
        {summary && (
          <button
            type="button"
            onClick={() => void show(true)}
            disabled={loading !== ''}
            title={t('settings.dailySummary.refineHint')}
            data-testid="summary-refine"
            className="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer disabled:cursor-default"
            style={buttonStyle}
          >
            {loading === 'refine' ? t('settings.dailySummary.refining') : t('settings.dailySummary.refine')}
          </button>
        )}
      </div>
      {summary && (
        <div
          className="text-sm mt-2 px-3 py-2 rounded-lg whitespace-pre-wrap"
          style={{ background: 'var(--color-bg-secondary)', color: 'var(--color-text)' }}
          data-testid="summary-text"
        >
          {summary.texto}
        </div>
      )}
      {summaryError && (
        <div className="text-xs mt-2 px-1" style={{ color: 'var(--color-error, #d33)' }}>
          {summaryError}
        </div>
      )}
      <div className="text-xs mt-2 px-1" style={{ color: 'var(--color-text-tertiary)' }}>
        {t('settings.dailySummary.hint')}
        {config?.ultimo_envio ? ` ${t('settings.dailySummary.lastSent', { date: config.ultimo_envio })}` : ''}
      </div>
      {error && (
        <div className="text-xs mt-2 px-1" style={{ color: 'var(--color-error, #d33)' }}>
          {error}
        </div>
      )}
    </>
  );
}
