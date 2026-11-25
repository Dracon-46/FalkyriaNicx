import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, CheckCircle2, Loader2, Stethoscope, XCircle } from 'lucide-react';
import { apiFetch } from '../../lib/api';

interface Check {
  id: string;
  estado: 'ok' | 'aviso' | 'falha';
  mensagem: string;
  dica: string;
}

interface Report {
  verificacoes: Check[];
  resumo: { ok: number; aviso: number; falha: number };
  segundos: number;
}

const ORDER: Record<Check['estado'], number> = { falha: 0, aviso: 1, ok: 2 };

function Icon({ estado }: { estado: Check['estado'] }) {
  if (estado === 'ok') return <CheckCircle2 size={14} style={{ color: 'var(--color-success)' }} />;
  if (estado === 'aviso') return <AlertTriangle size={14} style={{ color: 'var(--color-warning)' }} />;
  return <XCircle size={14} style={{ color: 'var(--color-error)' }} />;
}

/** Diagnóstico: verificações rápidas que não mudam nada (`GET /v1/diagnostico`). */
export function DiagnosticsSettings() {
  const { t, i18n } = useTranslation();
  const [report, setReport] = useState<Report | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');

  const run = async () => {
    setRunning(true);
    setError('');
    try {
      const res = await apiFetch('/v1/diagnostico');
      if (res.status === 404) throw new Error(t('settings.diagnostics.restartServer'));
      if (!res.ok) throw new Error(t('settings.diagnostics.failed'));
      setReport(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : t('settings.diagnostics.failed'));
    } finally {
      setRunning(false);
    }
  };

  const title = (id: string) => (i18n.exists(`settings.diagnostics.checks.${id}`) ? t(`settings.diagnostics.checks.${id}`) : id);
  const checks = report ? [...report.verificacoes].sort((a, b) => ORDER[a.estado] - ORDER[b.estado]) : [];

  return (
    <div className="py-3 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs max-w-md" style={{ color: 'var(--color-text-tertiary)' }}>
          {t('settings.diagnostics.description')}
        </p>
        <button
          type="button"
          onClick={() => void run()}
          disabled={running}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer disabled:opacity-50"
          style={{ background: 'var(--color-accent)', color: 'white' }}
          data-testid="diagnostics-run"
        >
          {running ? <Loader2 size={12} className="animate-spin" /> : <Stethoscope size={12} />}
          {running ? t('settings.diagnostics.running') : t('settings.diagnostics.run')}
        </button>
      </div>
      {error && (
        <p className="text-xs" role="alert" style={{ color: 'var(--color-error)' }}>
          {error}
        </p>
      )}
      {report && (
        <>
          <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }} data-testid="diagnostics-summary">
            {t('settings.diagnostics.summary', { ok: report.resumo.ok, aviso: report.resumo.aviso, falha: report.resumo.falha, s: report.segundos })}
          </p>
          <ul className="space-y-1.5">
            {checks.map((c, i) => (
              <li
                key={`${c.id}-${i}`}
                className="flex items-start gap-2 rounded-lg px-3 py-2"
                style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border-subtle)' }}
                data-testid={`diagnostics-${c.id}`}
              >
                <span className="mt-0.5 shrink-0">
                  <Icon estado={c.estado} />
                </span>
                <div className="min-w-0">
                  <div className="text-sm" style={{ color: 'var(--color-text)' }}>
                    {title(c.id)}
                  </div>
                  <div className="text-xs break-words" style={{ color: 'var(--color-text-secondary)' }}>
                    {c.mensagem}
                  </div>
                  {c.dica && (
                    <div className="text-xs mt-0.5 break-words" style={{ color: 'var(--color-text-tertiary)' }}>
                      {c.dica}
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
