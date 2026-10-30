import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { LANGUAGES } from '../../i18n';
import {
  fetchDictation,
  updateDictation,
  DictationUnsupportedError,
  type DictationChange,
  type DictationMode,
  type DictationStatus,
} from '../../lib/api';
import { ShortcutRecorder } from './ShortcutRecorder';

const STATES = ['desligado', 'pronto', 'ouvindo', 'transcrevendo', 'em_uso', 'sem_suporte', 'invalido', 'erro'];
const MODES: DictationMode[] = ['alternar', 'segurar'];

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

function Switch({ on, disabled, label, onClick }: { on: boolean; disabled: boolean; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
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

const selectStyle = { background: 'var(--color-bg)', border: '1px solid var(--color-border)', color: 'var(--color-text)' };

/** Ditado universal (`[ditado]`): atalho em qualquer programa, fala, e o texto é digitado. */
export function DictationSettings({ onSaved }: { onSaved: () => void }) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<DictationStatus | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const refresh = () =>
      fetchDictation()
        .then((s) => {
          if (cancelled) return;
          setStatus(s);
          setError('');
          timer = setTimeout(refresh, 5000);
        })
        .catch((e) => {
          if (cancelled) return;
          if (e instanceof DictationUnsupportedError) {
            setError(e.message);
            return;
          }
          setError(t('settings.dictation.serverUnavailable'));
          timer = setTimeout(refresh, 15000);
        });
    void refresh();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [t]);

  const change = async (update: DictationChange) => {
    setSaving(true);
    setError('');
    try {
      setStatus(await updateDictation(update));
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('settings.dictation.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  const ativo = status?.ativo ?? false;
  const estado = status?.estado ?? '';
  const busy = !status || saving;
  const problem = estado === 'em_uso' || estado === 'erro' || estado === 'invalido';
  const stateLabel = !status
    ? error || t('settings.dictation.checking')
    : STATES.includes(estado)
      ? t(`settings.dictation.states.${estado}`)
      : estado;
  const stateDescription = estado === 'em_uso'
    ? t('settings.dictation.inUseHint')
    : problem
      ? status?.mensagem
      : t('settings.dictation.statusDescription', { keys: status?.rotulo ?? '' });

  return (
    <>
      <Row label={t('settings.dictation.enableLabel')} description={t('settings.dictation.enableDescription')}>
        <Switch
          on={ativo}
          disabled={busy}
          label={t('settings.dictation.enableToggle')}
          onClick={() => void change({ ativo: !ativo })}
        />
      </Row>
      <Row label={t('settings.dictation.keysLabel')} description={t('settings.dictation.keysDescription')}>
        <ShortcutRecorder
          testId="dictation-recorder"
          value={status?.teclas ?? ''}
          disabled={busy}
          onChange={(teclas) => void change({ teclas })}
        />
      </Row>
      <Row label={t('settings.dictation.modeLabel')} description={t(`settings.dictation.modeDescriptions.${status?.modo ?? 'alternar'}`)}>
        <select
          value={status?.modo ?? 'alternar'}
          disabled={busy}
          aria-label={t('settings.dictation.modeLabel')}
          onChange={(e) => void change({ modo: e.target.value as DictationMode })}
          className="px-2 py-1 rounded text-xs"
          style={selectStyle}
          data-testid="dictation-mode"
        >
          {MODES.map((mode) => (
            <option key={mode} value={mode}>
              {t(`settings.dictation.modes.${mode}`)}
            </option>
          ))}
        </select>
      </Row>
      <Row label={t('settings.dictation.languageLabel')} description={t('settings.dictation.languageDescription')}>
        <select
          value={status?.idioma ?? ''}
          disabled={busy}
          aria-label={t('settings.dictation.languageLabel')}
          onChange={(e) => void change({ idioma: e.target.value })}
          className="px-2 py-1 rounded text-xs"
          style={selectStyle}
          data-testid="dictation-language"
        >
          <option value="">{t('settings.dictation.languageAuto')}</option>
          {LANGUAGES.map((language) => (
            <option key={language.code} value={language.code}>
              {language.name}
            </option>
          ))}
        </select>
      </Row>
      <Row label={t('settings.dictation.soundLabel')} description={t('settings.dictation.soundDescription')}>
        <Switch
          on={status?.som ?? true}
          disabled={busy}
          label={t('settings.dictation.soundLabel')}
          onClick={() => void change({ som: !(status?.som ?? true) })}
        />
      </Row>
      <Row label={t('settings.dictation.statusLabel')} description={stateDescription}>
        <div className="flex items-center gap-2">
          <span
            className="w-2 h-2 rounded-full"
            style={{
              background: estado === 'pronto' || estado === 'ouvindo' || estado === 'transcrevendo'
                ? 'var(--color-success)'
                : problem
                  ? 'var(--color-error, #d33)'
                  : 'var(--color-text-tertiary)',
            }}
          />
          <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }} data-testid="dictation-state">
            {stateLabel}
          </span>
        </div>
      </Row>
      <div className="text-xs mt-2 px-1" style={{ color: 'var(--color-text-tertiary)' }}>
        {t('settings.dictation.commandsHint')}
      </div>
      {error && status && (
        <div className="text-xs mt-2 px-1" style={{ color: 'var(--color-error, #d33)' }} role="alert">
          {error}
        </div>
      )}
    </>
  );
}
