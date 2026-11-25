import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../../lib/api';
import { ShortcutRecorder } from './ShortcutRecorder';

interface CaptureStatus {
  ativo: boolean;
  teclas: string;
  rotulo: string;
  estado: string;
  mensagem: string;
  suportado: boolean;
}

const STATES = ['desligado', 'registrado', 'em_uso', 'sem_suporte', 'invalido', 'erro'];

async function detail(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    return typeof body.detail === 'string' ? body.detail : '';
  } catch {
    return '';
  }
}

async function fetchCapture(): Promise<CaptureStatus> {
  const res = await apiFetch('/v1/captura');
  if (!res.ok) throw new Error(String(res.status));
  return res.json();
}

async function updateCapture(change: { ativo?: boolean; teclas?: string }): Promise<CaptureStatus> {
  const res = await apiFetch('/v1/captura', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(change),
  });
  if (!res.ok) throw new Error((await detail(res)) || String(res.status));
  return res.json();
}

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

/** Captura rápida (`[captura]`): um atalho guarda o texto selecionado nas notas. */
export function CaptureSettings({ onSaved }: { onSaved: () => void }) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<CaptureStatus | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchCapture()
      .then((s) => {
        if (!cancelled) setStatus(s);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error && e.message === '404' ? t('settings.capture.restartServer') : t('settings.capture.serverUnavailable'));
      });
    return () => {
      cancelled = true;
    };
  }, [t]);

  const change = async (update: { ativo?: boolean; teclas?: string }) => {
    setSaving(true);
    setError('');
    try {
      setStatus(await updateCapture(update));
      onSaved();
    } catch (e) {
      setError(e instanceof Error && e.message ? e.message : t('settings.capture.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  const ativo = status?.ativo ?? false;
  const estado = status?.estado ?? '';
  const busy = !status || saving;
  const problem = estado === 'em_uso' || estado === 'erro' || estado === 'invalido';

  return (
    <>
      <Row label={t('settings.capture.enableLabel')} description={t('settings.capture.enableDescription')}>
        <button
          type="button"
          role="switch"
          aria-checked={ativo}
          aria-label={t('settings.capture.enableLabel')}
          onClick={() => void change({ ativo: !ativo })}
          disabled={busy}
          className="relative w-11 h-6 rounded-full transition-colors cursor-pointer disabled:cursor-default"
          style={{ background: ativo ? 'var(--color-accent)' : 'var(--color-bg-tertiary)', opacity: busy ? 0.4 : 1 }}
          data-testid="capture-toggle"
        >
          <span
            className="absolute top-0.5 left-0.5 w-5 h-5 rounded-full transition-transform bg-white"
            style={{ transform: ativo ? 'translateX(20px)' : 'translateX(0)', boxShadow: '0 1px 3px rgba(0,0,0,0.2)' }}
          />
        </button>
      </Row>
      <Row label={t('settings.capture.keysLabel')} description={t('settings.capture.keysDescription')}>
        <ShortcutRecorder testId="capture-recorder" value={status?.teclas ?? ''} disabled={busy} onChange={(teclas) => void change({ teclas })} />
      </Row>
      <Row
        label={t('settings.capture.statusLabel')}
        description={estado === 'em_uso' ? t('settings.capture.inUseHint') : problem ? status?.mensagem : t('settings.capture.statusDescription', { keys: status?.rotulo ?? '' })}
      >
        <div className="flex items-center gap-2">
          <span
            className="w-2 h-2 rounded-full"
            style={{ background: estado === 'registrado' ? 'var(--color-success)' : problem ? 'var(--color-error, #d33)' : 'var(--color-text-tertiary)' }}
          />
          <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }} data-testid="capture-state">
            {!status ? error || t('settings.capture.checking') : STATES.includes(estado) ? t(`settings.capture.states.${estado}`) : estado}
          </span>
        </div>
      </Row>
      {error && status && (
        <div className="text-xs mt-2 px-1" style={{ color: 'var(--color-error, #d33)' }} role="alert">
          {error}
        </div>
      )}
    </>
  );
}
