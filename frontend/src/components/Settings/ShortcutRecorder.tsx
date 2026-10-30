import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  comboFromKeyEvent,
  formatCombo,
  formatPending,
  type ComboError,
  type Modifier,
} from '../../lib/shortcut';

/**
 * Campo que grava a combinação: clique, aperte as teclas juntas e solte.
 * Esc sozinho (ou sair do campo) cancela. Usado pelo atalho do Nicx e pelo
 * ditado.
 */
export function ShortcutRecorder({
  value,
  onChange,
  disabled = false,
  testId = 'shortcut-recorder',
}: {
  value: string;
  onChange: (combo: string) => void;
  disabled?: boolean;
  testId?: string;
}) {
  const { t } = useTranslation();
  const [recording, setRecording] = useState(false);
  const [pending, setPending] = useState<Modifier[]>([]);
  const [error, setError] = useState<ComboError | null>(null);
  const names = { space: t('settings.shortcut.keyNames.space') };

  const stop = () => {
    setRecording(false);
    setPending([]);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (!recording) return;
    e.preventDefault();
    e.stopPropagation();
    const result = comboFromKeyEvent(e);
    if (result.kind === 'pending') {
      setPending(result.modifiers);
      return;
    }
    if (result.kind === 'cancel') {
      setError(null);
      stop();
      return;
    }
    if (result.kind === 'error') {
      setError(result.reason);
      setPending([]);
      return;
    }
    setError(null);
    stop();
    if (result.combo !== value) onChange(result.combo);
  };

  const label = recording
    ? formatPending(pending) || t('settings.shortcut.recording')
    : formatCombo(value, names);

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        data-testid={testId}
        aria-label={t('settings.shortcut.record')}
        title={t('settings.shortcut.record')}
        disabled={disabled}
        onClick={() => {
          setError(null);
          setPending([]);
          setRecording(true);
        }}
        onKeyDown={onKeyDown}
        onKeyUp={(e) => {
          if (!recording) return;
          e.preventDefault();
          // Soltou todos os modificadores sem tecla principal: recomeça.
          if (!e.ctrlKey && !e.altKey && !e.shiftKey && !e.metaKey) setPending([]);
        }}
        onBlur={stop}
        className="min-w-36 px-3 py-1.5 rounded-lg text-xs font-mono cursor-pointer disabled:cursor-default"
        style={{
          background: 'var(--color-bg)',
          color: 'var(--color-text)',
          border: `1px solid ${recording ? 'var(--color-accent)' : 'var(--color-border)'}`,
          opacity: disabled ? 0.5 : 1,
        }}
      >
        {label}
      </button>
      {error && (
        <span className="text-[10px]" role="alert" style={{ color: 'var(--color-error, #d33)' }}>
          {t(`settings.shortcut.errors.${error}`)}
        </span>
      )}
    </div>
  );
}
