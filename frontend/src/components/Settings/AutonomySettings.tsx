import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, X } from 'lucide-react';
import {
  AUTONOMY_LEVELS,
  obterAutonomia,
  salvarAutonomia,
  type AutonomyLevel,
  type AutonomyState,
  type Risk,
} from '../../lib/historico';

const RISKS: Risk[] = ['leitura', 'leve', 'moderado', 'alto'];

/** Autonomia (`[autonomia]`): o que o Nicx faz sozinho e o que pede "confirmo". */
export function AutonomySettings({ onSaved }: { onSaved: () => void }) {
  const { t } = useTranslation();
  const [state, setState] = useState<AutonomyState | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    obterAutonomia()
      .then((s) => {
        if (!cancelled) setState(s);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : t('settings.autonomy.loadFailed'));
      });
    return () => {
      cancelled = true;
    };
  }, [t]);

  const choose = async (nivel: AutonomyLevel) => {
    if (!state || nivel === state.nivel) return;
    setSaving(true);
    setError('');
    try {
      setState(await salvarAutonomia(nivel));
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('settings.autonomy.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  const busy = !state || saving;
  const levels = state?.niveis.length ? state.niveis.map((n) => n.nivel) : [...AUTONOMY_LEVELS];
  const risks = state?.riscos.length ? state.riscos : RISKS;
  const allowed = (nivel: AutonomyLevel, risco: Risk) =>
    state?.niveis.find((n) => n.nivel === nivel)?.liberado.includes(risco) ?? false;

  return (
    <>
      <div className="text-xs mb-3" style={{ color: 'var(--color-text-tertiary)' }}>
        {t('settings.autonomy.description')}
      </div>
      <div className="grid gap-2 sm:grid-cols-3" role="radiogroup" aria-label={t('settings.autonomy.title')}>
        {levels.map((nivel) => {
          const on = state?.nivel === nivel;
          return (
            <button
              key={nivel}
              type="button"
              role="radio"
              aria-checked={on}
              disabled={busy}
              onClick={() => void choose(nivel)}
              data-testid={`autonomy-${nivel}`}
              className="text-left rounded-lg px-3 py-2.5 transition-colors cursor-pointer disabled:cursor-default"
              style={{
                background: on ? 'var(--color-accent-subtle)' : 'var(--color-bg-secondary)',
                border: `1px solid ${on ? 'var(--color-accent)' : 'var(--color-border)'}`,
                opacity: busy && !on ? 0.6 : 1,
              }}
            >
              <div className="flex items-center gap-2">
                <span
                  aria-hidden="true"
                  className="w-3.5 h-3.5 rounded-full shrink-0"
                  style={{
                    border: `2px solid ${on ? 'var(--color-accent)' : 'var(--color-border)'}`,
                    background: on ? 'var(--color-accent)' : 'transparent',
                    boxShadow: on ? 'inset 0 0 0 2px var(--color-bg)' : 'none',
                  }}
                />
                <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
                  {t(`settings.autonomy.levels.${nivel}.label`)}
                </span>
                {nivel === 'assistido' && (
                  <span className="text-[10px]" style={{ color: 'var(--color-text-tertiary)' }}>
                    {t('settings.autonomy.default')}
                  </span>
                )}
              </div>
              <div className="text-xs mt-1" style={{ color: 'var(--color-text-tertiary)' }}>
                {t(`settings.autonomy.levels.${nivel}.description`)}
              </div>
            </button>
          );
        })}
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-xs" data-testid="autonomy-matrix">
          <caption className="text-left text-sm mb-2" style={{ color: 'var(--color-text)' }}>
            {t('settings.autonomy.matrixTitle')}
          </caption>
          <thead>
            <tr style={{ color: 'var(--color-text-tertiary)' }}>
              <th className="text-start font-normal py-1 pe-3">{t('settings.autonomy.riskColumn')}</th>
              {levels.map((nivel) => (
                <th key={nivel} className="font-normal py-1 px-2 text-center">
                  {t(`settings.autonomy.levels.${nivel}.label`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {risks.map((risco) => (
              <tr key={risco} style={{ borderTop: '1px solid var(--color-border-subtle)' }}>
                <td className="py-1.5 pe-3 align-top">
                  <div style={{ color: 'var(--color-text)' }}>{t(`settings.autonomy.risks.${risco}.label`)}</div>
                  <div style={{ color: 'var(--color-text-tertiary)' }}>{t(`settings.autonomy.risks.${risco}.description`)}</div>
                </td>
                {levels.map((nivel) => {
                  const free = allowed(nivel, risco);
                  return (
                    <td
                      key={nivel}
                      className="py-1.5 px-2 text-center align-top"
                      data-testid={`autonomy-cell-${nivel}-${risco}`}
                      data-free={free}
                    >
                      <span
                        className="inline-flex items-center gap-1"
                        style={{ color: free ? 'var(--color-success)' : 'var(--color-text-tertiary)' }}
                        title={free ? t('settings.autonomy.free') : t('settings.autonomy.asks')}
                      >
                        {free ? <Check size={12} /> : <X size={12} />}
                        <span className="sr-only">{free ? t('settings.autonomy.free') : t('settings.autonomy.asks')}</span>
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="text-xs mt-2 px-1" style={{ color: 'var(--color-text-tertiary)' }}>
        {t('settings.autonomy.hint')}
      </div>
      {error && (
        <div className="text-xs mt-2 px-1" style={{ color: 'var(--color-error, #d33)' }}>
          {error}
        </div>
      )}
    </>
  );
}
