import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Palette,
  Globe,
  Cpu,
  Database,
  Info,
  Check,
  Sun,
  Moon,
  Monitor,
  Download,
  Upload,
  Trash2,
  Mic,
  Key,
  Search,
  Brain,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { LANGUAGES, setLanguage } from '../i18n';
import { useAppStore, type ThemeMode } from '../lib/store';
import { NicxMascot } from '../components/Mascot/NicxMascot';
import { PrivacySection } from '../components/Privacy/PrivacySection';
import { CalendarSettings } from '../components/Settings/CalendarSettings';
import { ContextSettings } from '../components/Settings/ContextSettings';
import { DailySummarySettings } from '../components/Settings/DailySummarySettings';
import {
  checkHealth,
  fetchSpeechHealth,
  fetchTtsHealth,
  fetchWakeStatus,
  updateWake,
  getMemoryStats,
  getInferenceSource,
  setInferenceSource,
  getCloudKeyStatus,
  saveCloudKey,
  fetchToolCredentialStatus,
  saveToolCredentials,
  deleteToolCredential,
  isTauri,
  type InferenceSource,
  type MemoryStats,
  type WakeStatus,
  WakeUnsupportedError,
  fetchShortcut,
  updateShortcut,
  type ShortcutAction,
  type ShortcutStatus,
  ShortcutUnsupportedError,
} from '../lib/api';
import { ShortcutRecorder } from '../components/Settings/ShortcutRecorder';
import { DictationSettings } from '../components/Settings/DictationSettings';

// Os testes e outras telas importam o campo daqui.
export { ShortcutRecorder };

const CLOUD_KEY_STATUS_CHANGED = 'nicx-cloud-key-status-changed';

function OllamaModelList() {
  const { t } = useTranslation();
  const [models, setModels] = useState<Array<{ name: string; size: number }>>([]);
  useEffect(() => {
    fetch('http://localhost:11434/api/tags')
      .then(r => r.json())
      .then(data => setModels((data.models || []).map((m: any) => ({ name: m.name, size: m.size }))))
      .catch(() => setModels([]));
  }, []);
  if (models.length === 0) return <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>{t('settings.models.none')}</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {models.map(m => (
        <span key={m.name} className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px]"
          style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text)' }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--color-success)', display: 'inline-block' }} />
          {m.name} ({(m.size / 1e9).toFixed(1)} GB)
        </span>
      ))}
    </div>
  );
}

function ApiKeyInput({
  keyName,
  placeholder,
  toolName,
}: {
  keyName: string;
  placeholder: string;
  toolName?: string;
}) {
  const { t } = useTranslation();
  const [value, setValue] = useState('');
  const [saved, setSaved] = useState(false);
  const [hasKey, setHasKey] = useState(false);
  const [error, setError] = useState('');
  const desktopKeyStorage = isTauri();
  const serverToolStorage = !desktopKeyStorage && !!toolName;
  const canManage = desktopKeyStorage || serverToolStorage;

  const refresh = useCallback(async () => {
    if (!canManage) {
      setHasKey(false);
      return;
    }
    try {
      const status = desktopKeyStorage
        ? await getCloudKeyStatus()
        : await fetchToolCredentialStatus(toolName!);
      setHasKey(!!status[keyName]);
    } catch {
      setHasKey(false);
    }
  }, [canManage, desktopKeyStorage, keyName, toolName]);

  useEffect(() => {
    void refresh();
    window.addEventListener(CLOUD_KEY_STATUS_CHANGED, refresh);
    return () => window.removeEventListener(CLOUD_KEY_STATUS_CHANGED, refresh);
  }, [refresh]);

  const save = async (v: string) => {
    const next = v.trim();
    if (!next) return;
    setError('');
    try {
      if (desktopKeyStorage) {
        await saveCloudKey(keyName, next);
      } else if (toolName) {
        await saveToolCredentials(toolName, { [keyName]: next });
      } else {
        return;
      }
      setValue('');
      setHasKey(true);
      setSaved(true);
      window.dispatchEvent(new Event(CLOUD_KEY_STATUS_CHANGED));
      setTimeout(() => setSaved(false), 2000);
    } catch (e: any) {
      setError(e?.message || t('settings.apiKeys.saveFailed'));
    }
  };

  const remove = async () => {
    setError('');
    try {
      if (desktopKeyStorage) {
        await saveCloudKey(keyName, '');
      } else if (toolName) {
        await deleteToolCredential(toolName, keyName);
      } else {
        return;
      }
      setValue('');
      setHasKey(false);
      setSaved(true);
      window.dispatchEvent(new Event(CLOUD_KEY_STATUS_CHANGED));
      setTimeout(() => setSaved(false), 2000);
    } catch (e: any) {
      setError(e?.message || t('settings.apiKeys.removeFailed'));
    }
  };

  return (
    <div className="flex items-center gap-2">
      <input
        type="password"
        value={value}
        onChange={e => setValue(e.target.value)}
        onBlur={() => { if (value.trim()) void save(value); }}
        placeholder={hasKey ? (desktopKeyStorage ? t('settings.apiKeys.savedSecure') : t('settings.apiKeys.savedServer')) : placeholder}
        disabled={!canManage}
        className="w-48 px-2 py-1 rounded text-xs"
        style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }} />
      {hasKey && (
        <button
          onClick={() => void remove()}
          className="px-2 py-1 rounded text-[10px] cursor-pointer"
          style={{ color: 'var(--color-error)', border: '1px solid var(--color-error)' }}
        >
          {t('settings.apiKeys.remove')}
        </button>
      )}
      {saved && <span className="text-[10px]" style={{ color: 'var(--color-success)' }}>{t('settings.apiKeys.saved')}</span>}
      {error && <span className="text-[10px]" style={{ color: 'var(--color-error)' }}>{error}</span>}
    </div>
  );
}

function CloudProviderStatus({ label, keyName }: { label: string; keyName: string }) {
  const [hasKey, setHasKey] = useState(false);
  const desktopKeyStorage = isTauri();

  const refresh = useCallback(async () => {
    if (!desktopKeyStorage) {
      setHasKey(false);
      return;
    }
    try {
      const status = await getCloudKeyStatus();
      setHasKey(!!status[keyName]);
    } catch {
      setHasKey(false);
    }
  }, [desktopKeyStorage, keyName]);

  useEffect(() => {
    void refresh();
    window.addEventListener(CLOUD_KEY_STATUS_CHANGED, refresh);
    return () => window.removeEventListener(CLOUD_KEY_STATUS_CHANGED, refresh);
  }, [refresh]);

  return (
    <span className="flex items-center gap-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
      <span style={{
        width: 6, height: 6, borderRadius: '50%', display: 'inline-block',
        background: hasKey ? 'var(--color-success)' : 'var(--color-text-tertiary)',
      }} />
      {label}
    </span>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      className="rounded-xl p-5"
      style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
    >
      <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--color-text)' }}>
        {title}
      </h3>
      {children}
    </div>
  );
}

function SettingRow({ label, description, children }: { label: string; description?: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between py-3" style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
      <div className="min-w-0">
        <div className="text-sm" style={{ color: 'var(--color-text)' }}>{label}</div>
        {description && (
          <div className="text-xs mt-0.5 break-words" style={{ color: 'var(--color-text-tertiary)' }}>{description}</div>
        )}
      </div>
      <div>{children}</div>
    </div>
  );
}


function Toggle({
  on,
  onClick,
  disabled = false,
  label,
}: {
  on: boolean;
  onClick: () => void;
  disabled?: boolean;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
      className="relative w-11 h-6 rounded-full transition-colors cursor-pointer disabled:cursor-default"
      style={{
        background: on ? 'var(--color-accent)' : 'var(--color-bg-tertiary)',
        opacity: disabled ? 0.4 : 1,
      }}
    >
      <span
        className="absolute top-0.5 left-0.5 w-5 h-5 rounded-full transition-transform bg-white"
        style={{
          transform: on ? 'translateX(20px)' : 'translateX(0)',
          boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
        }}
      />
    </button>
  );
}

/** Estado vindo do servidor -> chave do texto (settings.wake.states.*). */
const WAKE_STATE_KEY: Record<string, string> = {
  escutando: 'listening',
  pausado: 'paused',
  'mascote aberto': 'mascotOpen',
  parado: 'stopped',
};

/** "Nicx, ligar": opt-in background listener that brings the mascot up. */
export function WakeWordSettings({ onSaved }: { onSaved: () => void }) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<WakeStatus | null>(null);
  const [error, setError] = useState('');
  const [unsupported, setUnsupported] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const refresh = () =>
      fetchWakeStatus()
        .then((s) => {
          if (cancelled) return;
          setStatus(s);
          setError('');
          setUnsupported(false);
          timer = setTimeout(refresh, 5000);
        })
        .catch((e) => {
          if (cancelled) return;
          // An older server: say so once and stop asking.
          if (e instanceof WakeUnsupportedError) {
            setUnsupported(true);
            setError(e.message);
            return;
          }
          setError(t('settings.wake.serverUnavailable'));
          timer = setTimeout(refresh, 10000);
        });
    void refresh();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [t]);

  const change = async (update: { enabled?: boolean; autostart?: boolean }) => {
    setSaving(true);
    setError('');
    try {
      setStatus(await updateWake(update));
      onSaved();
    } catch (e) {
      if (e instanceof WakeUnsupportedError) setUnsupported(true);
      setError(e instanceof Error ? e.message : t('settings.wake.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  const enabled = status?.enabled ?? false;
  const stateLabel = unsupported
    ? t('settings.wake.restartServer')
    : !status
    ? error || t('settings.wake.checking')
    : enabled && !status.running
      ? t('settings.wake.starting')
      : WAKE_STATE_KEY[status.state]
        ? t(`settings.wake.states.${WAKE_STATE_KEY[status.state]}`)
        : status.state;

  return (
    <>
      <SettingRow
        label={t('settings.wake.enableLabel')}
        description={t('settings.wake.enableDescription')}
      >
        <Toggle
          on={enabled}
          disabled={!status || saving}
          label={t('settings.wake.enableToggle')}
          onClick={() => void change({ enabled: !enabled })}
        />
      </SettingRow>
      <SettingRow
        label={t('settings.wake.listening')}
        description={
          status && !status.window_supported
            ? t('settings.wake.noWindow')
            : t('settings.wake.howToStop')
        }
      >
        <div className="flex items-center gap-2">
          <span
            className="w-2 h-2 rounded-full"
            style={{
              background: status?.running ? 'var(--color-success)' : 'var(--color-text-tertiary)',
            }}
          />
          <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }} data-testid="wake-state">
            {stateLabel}
          </span>
        </div>
      </SettingRow>
      {status?.autostart_supported && (
        <SettingRow label={t('settings.wake.autostart')} description={t('settings.wake.autostartDescription')}>
          <Toggle
            on={status.autostart}
            disabled={saving}
            label={t('settings.wake.autostart')}
            onClick={() => void change({ autostart: !status.autostart })}
          />
        </SettingRow>
      )}
      {error && (status || unsupported) && (
        <div className="text-xs mt-2 px-1" style={{ color: 'var(--color-error, #d33)' }}>
          {error}
        </div>
      )}
    </>
  );
}

const SHORTCUT_STATES = ['registrado', 'em_uso', 'desligado', 'sem_suporte', 'invalido', 'erro'];

/** Atalho global de teclado (`[atalho]`): chama o Nicx de qualquer janela. */
export function ShortcutSettings({ onSaved }: { onSaved: () => void }) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<ShortcutStatus | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const refresh = () =>
      fetchShortcut()
        .then((s) => {
          if (cancelled) return;
          setStatus(s);
          setError('');
          timer = setTimeout(refresh, 15000);
        })
        .catch((e) => {
          if (cancelled) return;
          if (e instanceof ShortcutUnsupportedError) {
            setError(e.message);
            return;
          }
          setError(t('settings.shortcut.serverUnavailable'));
          timer = setTimeout(refresh, 15000);
        });
    void refresh();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [t]);

  const change = async (update: { ativo?: boolean; teclas?: string; acao?: ShortcutAction }) => {
    setSaving(true);
    setError('');
    try {
      setStatus(await updateShortcut(update));
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('settings.shortcut.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  const ativo = status?.ativo ?? false;
  const estado = status?.estado ?? '';
  const stateLabel = !status
    ? error || t('settings.shortcut.checking')
    : SHORTCUT_STATES.includes(estado)
      ? t(`settings.shortcut.states.${estado}`)
      : estado;
  const problem = estado === 'em_uso' || estado === 'erro' || estado === 'invalido';
  const stateDescription = estado === 'em_uso'
    ? t('settings.shortcut.inUseHint')
    : problem
      ? status?.mensagem
      : t('settings.shortcut.statusDescription');

  return (
    <>
      <SettingRow label={t('settings.shortcut.enableLabel')} description={t('settings.shortcut.enableDescription')}>
        <Toggle
          on={ativo}
          disabled={!status || saving}
          label={t('settings.shortcut.enableToggle')}
          onClick={() => void change({ ativo: !ativo })}
        />
      </SettingRow>
      <SettingRow label={t('settings.shortcut.keysLabel')} description={t('settings.shortcut.keysDescription')}>
        <ShortcutRecorder
          value={status?.teclas ?? ''}
          disabled={!status || saving}
          onChange={(teclas) => void change({ teclas })}
        />
      </SettingRow>
      <SettingRow label={t('settings.shortcut.actionLabel')} description={t('settings.shortcut.actionDescription')}>
        <select
          value={status?.acao ?? 'flutuante'}
          disabled={!status || saving}
          aria-label={t('settings.shortcut.actionLabel')}
          onChange={(e) => void change({ acao: e.target.value as ShortcutAction })}
          className="px-2 py-1 rounded text-xs"
          style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
        >
          <option value="flutuante">{t('settings.shortcut.actions.flutuante')}</option>
          <option value="app">{t('settings.shortcut.actions.app')}</option>
        </select>
      </SettingRow>
      <SettingRow label={t('settings.shortcut.statusLabel')} description={stateDescription}>
        <div className="flex items-center gap-2">
          <span
            className="w-2 h-2 rounded-full"
            style={{
              background: estado === 'registrado'
                ? 'var(--color-success)'
                : problem
                  ? 'var(--color-error, #d33)'
                  : 'var(--color-text-tertiary)',
            }}
          />
          <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }} data-testid="shortcut-state">
            {stateLabel}
          </span>
        </div>
      </SettingRow>
      {error && status && (
        <div className="text-xs mt-2 px-1" style={{ color: 'var(--color-error, #d33)' }}>
          {error}
        </div>
      )}
    </>
  );
}

type MemoryStatus =
  | { kind: 'loading' }
  | { kind: 'ready'; stats: MemoryStats }
  | { kind: 'error'; message: string };

export function MemoryStatusRow({
  status,
  onRetry,
}: {
  status: MemoryStatus;
  onRetry: () => void;
}) {
  const { t } = useTranslation();
  const stats = status.kind === 'ready' ? status.stats : null;
  const description = status.kind === 'error'
    ? status.message
    : status.kind === 'loading'
      ? t('settings.memory.checkingBackend')
      : stats?.backend === 'none'
        ? t('settings.memory.notConfiguredLong')
        : t('settings.memory.backendEntries', { backend: stats?.backend, entries: stats?.entries });
  const label = status.kind === 'loading'
    ? t('settings.memory.checking')
    : stats?.backend === 'none'
      ? t('settings.memory.notConfigured')
      : stats
        ? t('settings.memory.entries', { entries: stats.entries })
        : t('settings.memory.unavailable');

  return (
    <SettingRow label={t('settings.memory.status')} description={description}>
      <div className="flex items-center gap-2">
        <Brain size={14} style={{ color: stats && stats.backend !== 'none' ? 'var(--color-accent)' : 'var(--color-text-tertiary)' }} />
        <span className="text-xs whitespace-nowrap" style={{ color: 'var(--color-text-secondary)' }}>
          {label}
        </span>
        {status.kind === 'error' && (
          <button
            type="button"
            onClick={onRetry}
            className="text-xs underline cursor-pointer whitespace-nowrap"
            style={{ color: 'var(--color-accent)' }}
          >
            {t('settings.memory.retry')}
          </button>
        )}
      </div>
    </SettingRow>
  );
}

const themeOptions: { value: ThemeMode; label: string; icon: typeof Sun }[] = [
  { value: 'light', label: 'settings.theme.light', icon: Sun },
  { value: 'dark', label: 'settings.theme.dark', icon: Moon },
  { value: 'system', label: 'settings.theme.system', icon: Monitor },
];

export function SettingsPage() {
  const settings = useAppStore((s) => s.settings);
  const updateSettings = useAppStore((s) => s.updateSettings);
  const { t } = useTranslation();
  const conversations = useAppStore((s) => s.conversations);
  const serverInfo = useAppStore((s) => s.serverInfo);
  const [healthy, setHealthy] = useState<boolean | null>(null);
  const [speechBackendAvailable, setSpeechBackendAvailable] = useState<boolean | null>(null);
  const [ttsBackend, setTtsBackend] = useState<{ available: boolean; backend?: string; voice_id?: string } | null>(null);
  const [saved, setSaved] = useState(false);

  const [memoryStatus, setMemoryStatus] = useState<MemoryStatus>({ kind: 'loading' });
  const memoryRequestId = useRef(0);
  const [memoryEnabled, setMemoryEnabled] = useState(() => {
    try { return localStorage.getItem('nicx-memory-enabled') !== 'false'; } catch { return true; }
  });
  const [memoryBackend, setMemoryBackend] = useState(() => {
    try { return localStorage.getItem('nicx-memory-backend') || 'sqlite'; } catch { return 'sqlite'; }
  });
  const [memoryTopK, setMemoryTopK] = useState(() => {
    try { return parseInt(localStorage.getItem('nicx-memory-top-k') || '5'); } catch { return 5; }
  });
  const [memoryMinScore, setMemoryMinScore] = useState(() => {
    try { return parseFloat(localStorage.getItem('nicx-memory-min-score') || '0.1'); } catch { return 0.1; }
  });
  const [memoryMaxTokens, setMemoryMaxTokens] = useState(() => {
    try { return parseInt(localStorage.getItem('nicx-memory-max-tokens') || '2048'); } catch { return 2048; }
  });

  const [srcKind, setSrcKind] = useState<InferenceSource['kind']>('ollama');
  const [customHost, setCustomHost] = useState('http://localhost:1234/v1');
  const [customModel, setCustomModel] = useState('');
  const [customEngine, setCustomEngine] = useState('lmstudio');
  const [customKey, setCustomKey] = useState('');
  const [srcMsg, setSrcMsg] = useState('');

  useEffect(() => {
    getInferenceSource().then((s) => {
      setSrcKind(s.kind);
      if (s.host) setCustomHost(s.host);
      if (s.model) setCustomModel(s.model);
      if (s.engine) setCustomEngine(s.engine);
    }).catch(() => {});
  }, []);

  const saveSource = useCallback(async () => {
    try {
      if (srcKind === 'custom') {
        await setInferenceSource({ kind: 'custom', host: customHost, model: customModel, engine: customEngine, apiKey: customKey || undefined });
      } else {
        await setInferenceSource({ kind: 'ollama' });
      }
      setSrcMsg(t('settings.inference.saved'));
    } catch (e: any) {
      setSrcMsg(e?.message ?? t('settings.inference.saveFailed'));
    }
  }, [srcKind, customHost, customModel, customEngine, customKey, t]);

  const refreshMemoryStatus = useCallback(async () => {
    const requestId = ++memoryRequestId.current;
    setMemoryStatus({ kind: 'loading' });
    try {
      const stats = await getMemoryStats();
      if (requestId === memoryRequestId.current) {
        setMemoryStatus({ kind: 'ready', stats });
      }
    } catch (error) {
      if (requestId === memoryRequestId.current) {
        setMemoryStatus({
          kind: 'error',
          message: error instanceof Error ? error.message : String(error),
        });
      }
    }
  }, []);

  useEffect(() => {
    void refreshMemoryStatus();
    const onFocus = () => { void refreshMemoryStatus(); };
    window.addEventListener('focus', onFocus);
    return () => {
      window.removeEventListener('focus', onFocus);
      ++memoryRequestId.current;
    };
  }, [refreshMemoryStatus, settings.apiUrl]);

  useEffect(() => {
    checkHealth().then(setHealthy);
    fetchSpeechHealth()
      .then((h) => setSpeechBackendAvailable(h.available))
      .catch(() => setSpeechBackendAvailable(false));
    fetchTtsHealth()
      .then((h) => setTtsBackend(h))
      .catch(() => setTtsBackend({ available: false }));
  }, []);

  const showSaved = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  const handleExport = () => {
    const data = localStorage.getItem('nicx-conversations') || '{}';
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `nicx-export-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleImport = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        try {
          const data = JSON.parse(ev.target?.result as string);
          if (data.version === 1) {
            localStorage.setItem('nicx-conversations', JSON.stringify(data));
            useAppStore.getState().loadConversations();
            showSaved();
          }
        } catch {}
      };
      reader.readAsText(file);
    };
    input.click();
  };

  const [confirmClear, setConfirmClear] = useState(false);
  const handleClear = () => {
    if (!confirmClear) {
      setConfirmClear(true);
      setTimeout(() => setConfirmClear(false), 3000);
      return;
    }
    localStorage.removeItem('nicx-conversations');
    useAppStore.getState().loadConversations();
    setConfirmClear(false);
    showSaved();
  };

  return (
    <div className="flex-1 overflow-y-auto px-6 py-10">
      <div className="max-w-2xl mx-auto">
        <header className="mb-6">
          <div className="flex items-center justify-between gap-3">
            <h1 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
              {t('settings.page.title')}
            </h1>
            {saved && (
              <span className="flex items-center gap-1 text-xs px-2 py-1 rounded-full" style={{
                background: 'var(--color-accent-subtle)',
                color: 'var(--color-success)',
              }}>
                <Check size={12} /> {t('settings.page.saved')}
              </span>
            )}
          </div>
          <p className="text-sm mt-2 max-w-2xl" style={{ color: 'var(--color-text-secondary)' }}>
            {t('settings.page.description')}
          </p>
        </header>

        <div className="flex flex-col gap-4">
          {/* Appearance */}
          <Section title={t('settings.sections.appearance')}>
            <SettingRow label={t('settings.language.label')} description={t('settings.language.description')}>
              <select
                value={settings.language}
                onChange={(e) => {
                  updateSettings({ language: e.target.value });
                  void setLanguage(e.target.value);
                  showSaved();
                }}
                aria-label={t('settings.language.label')}
                className="text-sm px-3 py-1.5 rounded-lg outline-none cursor-pointer"
                style={{
                  background: 'var(--color-bg-secondary)',
                  color: 'var(--color-text)',
                  border: '1px solid var(--color-border)',
                }}
              >
                {LANGUAGES.map((lang) => (
                  <option key={lang.code} value={lang.code} lang={lang.code}>
                    {lang.name}
                  </option>
                ))}
              </select>
            </SettingRow>
            <SettingRow label={t('settings.theme.label')} description={t('settings.theme.description')}>
              <div className="flex gap-1 p-0.5 rounded-lg" style={{ background: 'var(--color-bg-secondary)' }}>
                {themeOptions.map((opt) => {
                  const isActive = settings.theme === opt.value;
                  return (
                    <button
                      key={opt.value}
                      onClick={() => { updateSettings({ theme: opt.value }); showSaved(); }}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer"
                      style={{
                        background: isActive ? 'var(--color-surface)' : 'transparent',
                        color: isActive ? 'var(--color-text)' : 'var(--color-text-tertiary)',
                        boxShadow: isActive ? 'var(--shadow-sm)' : 'none',
                      }}
                    >
                      <opt.icon size={14} />
                      {t(opt.label)}
                    </button>
                  );
                })}
              </div>
            </SettingRow>
            <SettingRow label={t('settings.fontSize.label')}>
              <select
                value={settings.fontSize}
                onChange={(e) => { updateSettings({ fontSize: e.target.value as any }); showSaved(); }}
                className="text-sm px-3 py-1.5 rounded-lg outline-none cursor-pointer"
                style={{
                  background: 'var(--color-bg-secondary)',
                  color: 'var(--color-text)',
                  border: '1px solid var(--color-border)',
                }}
              >
                <option value="small">{t('settings.fontSize.small')}</option>
                <option value="default">{t('settings.fontSize.default')}</option>
                <option value="large">{t('settings.fontSize.large')}</option>
              </select>
            </SettingRow>
          </Section>

          {/* Connection */}
          <Section title={t('settings.sections.connection')}>
            <SettingRow label={t('settings.connection.serverStatus')} description={serverInfo ? `${serverInfo.engine} / ${serverInfo.model}` : t('settings.connection.notConnected')}>
              <div className="flex items-center gap-2">
                <span
                  className="w-2 h-2 rounded-full"
                  style={{ background: healthy === true ? 'var(--color-success)' : healthy === false ? 'var(--color-error)' : 'var(--color-text-tertiary)' }}
                />
                <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                  {healthy === true ? t('settings.connection.connected') : healthy === false ? t('settings.connection.disconnected') : t('settings.connection.checking')}
                </span>
              </div>
            </SettingRow>
            <SettingRow
              label={t('settings.connection.serverAddress')}
              description={
                settings.apiUrl && !/^https?:\/\/[^\s/]+/i.test(settings.apiUrl.trim())
                  ? t('settings.connection.invalidAddress')
                  : t('settings.connection.addressHint')
              }
            >
              <input
                type="url"
                value={settings.apiUrl}
                onChange={(e) => { updateSettings({ apiUrl: e.target.value }); showSaved(); }}
                placeholder={t('settings.connection.addressPlaceholder')}
                aria-invalid={Boolean(settings.apiUrl) && !/^https?:\/\/[^\s/]+/i.test(settings.apiUrl.trim())}
                className="text-sm px-3 py-1.5 rounded-lg outline-none w-56"
                style={{
                  background: 'var(--color-bg-secondary)',
                  color: 'var(--color-text)',
                  border: '1px solid var(--color-border)',
                }}
              />
            </SettingRow>
            <SettingRow label={t('settings.connection.apiKey')} description={t('settings.connection.apiKeyDescription')}>
              <input
                type="password"
                value={settings.apiKey}
                onChange={(e) => { updateSettings({ apiKey: e.target.value }); showSaved(); }}
                placeholder="NICX_API_KEY"
                autoComplete="off"
                className="text-sm px-3 py-1.5 rounded-lg outline-none w-56"
                style={{
                  background: 'var(--color-bg-secondary)',
                  color: 'var(--color-text)',
                  border: '1px solid var(--color-border)',
                }}
              />
            </SettingRow>
          </Section>

          {/* Inference source */}
          <Section title={t('settings.sections.inference')}>
            <SettingRow label={t('settings.inference.source')} description={t('settings.inference.sourceDescription')}>
              <select
                value={srcKind}
                onChange={(e) => { setSrcKind(e.target.value as InferenceSource['kind']); setSrcMsg(''); }}
                className="text-sm px-3 py-1.5 rounded-lg outline-none w-56"
                style={{ background: 'var(--color-bg-secondary)', color: 'var(--color-text)', border: '1px solid var(--color-border)' }}
              >
                <option value="ollama">{t('settings.inference.ollama')}</option>
                <option value="custom">{t('settings.inference.custom')}</option>
              </select>
            </SettingRow>
            {srcKind === 'custom' && (
              <>
                <SettingRow label={t('settings.inference.serverUrl')} description={t('settings.inference.serverUrlDescription')}>
                  <input type="text" value={customHost} onChange={(e) => { setCustomHost(e.target.value); setSrcMsg(''); }} placeholder="http://localhost:1234/v1"
                    className="text-sm px-3 py-1.5 rounded-lg outline-none w-56"
                    style={{ background: 'var(--color-bg-secondary)', color: 'var(--color-text)', border: '1px solid var(--color-border)' }} />
                </SettingRow>
                <SettingRow label={t('settings.inference.model')} description={t('settings.inference.modelDescription')}>
                  <input type="text" value={customModel} onChange={(e) => { setCustomModel(e.target.value); setSrcMsg(''); }} placeholder="qwen2.5-7b-instruct"
                    className="text-sm px-3 py-1.5 rounded-lg outline-none w-56"
                    style={{ background: 'var(--color-bg-secondary)', color: 'var(--color-text)', border: '1px solid var(--color-border)' }} />
                </SettingRow>
                <SettingRow label={t('settings.inference.serverType')} description={t('settings.inference.serverTypeDescription')}>
                  <select value={customEngine} onChange={(e) => { setCustomEngine(e.target.value); setSrcMsg(''); }}
                    className="text-sm px-3 py-1.5 rounded-lg outline-none w-56"
                    style={{ background: 'var(--color-bg-secondary)', color: 'var(--color-text)', border: '1px solid var(--color-border)' }}>
                    <option value="lmstudio">LM Studio</option>
                    <option value="vllm">vLLM</option>
                    <option value="sglang">SGLang</option>
                    <option value="llamacpp">llama.cpp</option>
                    <option value="mlx">MLX</option>
                  </select>
                </SettingRow>
                <SettingRow label={t('settings.inference.apiKey')} description={t('settings.inference.apiKeyDescription')}>
                  <input type="password" value={customKey} onChange={(e) => { setCustomKey(e.target.value); setSrcMsg(''); }} placeholder={t('settings.inference.apiKeyPlaceholder')}
                    className="text-sm px-3 py-1.5 rounded-lg outline-none w-56"
                    style={{ background: 'var(--color-bg-secondary)', color: 'var(--color-text)', border: '1px solid var(--color-border)' }} />
                </SettingRow>
              </>
            )}
            <SettingRow label="" description={srcMsg}>
              <button onClick={saveSource}
                className="text-sm px-3 py-1.5 rounded-lg outline-none cursor-pointer"
                style={{ background: 'var(--color-accent, var(--color-bg-tertiary))', color: 'var(--color-text)', border: '1px solid var(--color-border)' }}>
                {t('settings.inference.save')}
              </button>
            </SettingRow>
          </Section>

          {/* Models */}
          <Section title={t('settings.sections.models')}>
            <SettingRow label={t('settings.models.local')} description={t('settings.models.localDescription')}>
              <OllamaModelList />
            </SettingRow>
            <div className="text-xs mt-2 px-1" style={{ color: 'var(--color-text-tertiary)' }}>
              {t('settings.models.pullBefore')} <code className="px-1 py-0.5 rounded text-[11px]" style={{ background: 'var(--color-bg-tertiary)' }}>ollama pull &lt;{t('settings.models.pullModelName')}&gt;</code> {t('settings.models.pullAfter')}
            </div>
            <SettingRow label={t('settings.models.cloud')} description={t('settings.models.cloudDescription')}>
              <div className="flex flex-wrap gap-3">
                <CloudProviderStatus label="OpenAI" keyName="OPENAI_API_KEY" />
                <CloudProviderStatus label="Anthropic" keyName="ANTHROPIC_API_KEY" />
                <CloudProviderStatus label="Google" keyName="GEMINI_API_KEY" />
                <CloudProviderStatus label="OpenRouter" keyName="OPENROUTER_API_KEY" />
                <CloudProviderStatus label="Atlas Cloud" keyName="ATLASCLOUD_API_KEY" />
              </div>
            </SettingRow>
          </Section>

          {/* API Keys */}
          <Section title={t('settings.sections.apiKeys')}>
            <SettingRow label="OpenAI" description={t('settings.apiKeys.openaiDescription')}>
              <ApiKeyInput keyName="OPENAI_API_KEY" placeholder="sk-..." />
            </SettingRow>
            <SettingRow label="Anthropic" description={t('settings.apiKeys.anthropicDescription')}>
              <ApiKeyInput keyName="ANTHROPIC_API_KEY" placeholder="sk-ant-..." />
            </SettingRow>
            <SettingRow label="Google" description={t('settings.apiKeys.googleDescription')}>
              <ApiKeyInput keyName="GEMINI_API_KEY" placeholder="AI..." />
            </SettingRow>
            <SettingRow label="OpenRouter" description={t('settings.apiKeys.openrouterDescription')}>
              <ApiKeyInput keyName="OPENROUTER_API_KEY" placeholder="sk-or-..." />
            </SettingRow>
            <SettingRow label="Atlas Cloud" description={t('settings.apiKeys.atlasDescription')}>
              <ApiKeyInput keyName="ATLASCLOUD_API_KEY" placeholder={t('settings.apiKeys.atlasPlaceholder')} />
            </SettingRow>
          </Section>

          {/* Tools */}
          <Section title={t('settings.sections.tools')}>
            <SettingRow label={t('settings.tools.webSearch')} description={t('settings.tools.webSearchDescription')}>
              <ApiKeyInput keyName="TAVILY_API_KEY" placeholder="tvly-..." toolName="web_search" />
            </SettingRow>
          </Section>

          {/* Memory */}
          <Section title={t('settings.sections.memory')}>
            <MemoryStatusRow status={memoryStatus} onRetry={() => { void refreshMemoryStatus(); }} />
            <SettingRow label={t('settings.memory.useContext')} description={t('settings.memory.useContextDescription')}>
              <button
                onClick={() => {
                  const next = !memoryEnabled;
                  setMemoryEnabled(next);
                  try { localStorage.setItem('nicx-memory-enabled', String(next)); } catch {}
                  showSaved();
                }}
                className="relative w-11 h-6 rounded-full transition-colors cursor-pointer"
                style={{
                  background: memoryEnabled ? 'var(--color-accent)' : 'var(--color-bg-tertiary)',
                }}
              >
                <span
                  className="absolute top-0.5 left-0.5 w-5 h-5 rounded-full transition-transform bg-white"
                  style={{
                    transform: memoryEnabled ? 'translateX(20px)' : 'translateX(0)',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
                  }}
                />
              </button>
            </SettingRow>
            <SettingRow label={t('settings.memory.backend')} description={t('settings.memory.backendDescription')}>
              <select
                value={memoryBackend}
                onChange={(e) => {
                  setMemoryBackend(e.target.value);
                  try { localStorage.setItem('nicx-memory-backend', e.target.value); } catch {}
                  showSaved();
                }}
                className="text-sm px-3 py-1.5 rounded-lg outline-none cursor-pointer"
                style={{
                  background: 'var(--color-bg-secondary)',
                  color: 'var(--color-text)',
                  border: '1px solid var(--color-border)',
                }}
              >
                <option value="sqlite">sqlite</option>
                <option value="faiss">faiss</option>
                <option value="bm25">bm25</option>
                <option value="colbert">colbert</option>
                <option value="hybrid">hybrid</option>
              </select>
            </SettingRow>
            <SettingRow label={t('settings.memory.topK')} description={`${memoryTopK}`}>
              <input
                type="range"
                min="1"
                max="20"
                step="1"
                value={memoryTopK}
                onChange={(e) => {
                  const v = parseInt(e.target.value);
                  setMemoryTopK(v);
                  try { localStorage.setItem('nicx-memory-top-k', String(v)); } catch {}
                  showSaved();
                }}
                className="w-32 cursor-pointer accent-[var(--color-accent)]"
              />
            </SettingRow>
            <SettingRow label={t('settings.memory.minScore')} description={`${memoryMinScore}`}>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={memoryMinScore}
                onChange={(e) => {
                  const v = parseFloat(e.target.value);
                  setMemoryMinScore(v);
                  try { localStorage.setItem('nicx-memory-min-score', String(v)); } catch {}
                  showSaved();
                }}
                className="w-32 cursor-pointer accent-[var(--color-accent)]"
              />
            </SettingRow>
            <SettingRow label={t('settings.memory.maxTokens')} description={`${memoryMaxTokens}`}>
              <input
                type="range"
                min="256"
                max="8192"
                step="256"
                value={memoryMaxTokens}
                onChange={(e) => {
                  const v = parseInt(e.target.value);
                  setMemoryMaxTokens(v);
                  try { localStorage.setItem('nicx-memory-max-tokens', String(v)); } catch {}
                  showSaved();
                }}
                className="w-32 cursor-pointer accent-[var(--color-accent)]"
              />
            </SettingRow>
          </Section>

          {/* Model defaults */}
          <Section title={t('settings.sections.modelDefaults')}>
            <SettingRow label={t('settings.modelDefaults.temperature')} description={`${settings.temperature}`}>
              <input
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={settings.temperature}
                onChange={(e) => { updateSettings({ temperature: parseFloat(e.target.value) }); showSaved(); }}
                className="w-32 cursor-pointer accent-[var(--color-accent)]"
              />
            </SettingRow>
            <SettingRow label={t('settings.modelDefaults.maxTokens')} description={`${settings.maxTokens}`}>
              <input
                type="range"
                min="256"
                max="32768"
                step="256"
                value={settings.maxTokens}
                onChange={(e) => { updateSettings({ maxTokens: parseInt(e.target.value) }); showSaved(); }}
                className="w-32 cursor-pointer accent-[var(--color-accent)]"
              />
            </SettingRow>
          </Section>

          {/* Speech */}
          <Section title={t('settings.sections.voice')}>
            <SettingRow label={t('settings.voice.input')} description={t('settings.voice.inputDescription')}>
              <button
                onClick={() => { updateSettings({ speechEnabled: !settings.speechEnabled }); showSaved(); }}
                className="relative w-11 h-6 rounded-full transition-colors cursor-pointer"
                style={{
                  background: settings.speechEnabled ? 'var(--color-accent)' : 'var(--color-bg-tertiary)',
                }}
              >
                <span
                  className="absolute top-0.5 left-0.5 w-5 h-5 rounded-full transition-transform bg-white"
                  style={{
                    transform: settings.speechEnabled ? 'translateX(20px)' : 'translateX(0)',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
                  }}
                />
              </button>
            </SettingRow>
            <SettingRow label={t('settings.voice.output')} description={t('settings.voice.outputDescription')}>
              <button
                onClick={() => { updateSettings({ voiceOutputEnabled: !settings.voiceOutputEnabled }); showSaved(); }}
                className="relative w-11 h-6 rounded-full transition-colors cursor-pointer"
                style={{
                  background: settings.voiceOutputEnabled ? 'var(--color-accent)' : 'var(--color-bg-tertiary)',
                }}
              >
                <span
                  className="absolute top-0.5 left-0.5 w-5 h-5 rounded-full transition-transform bg-white"
                  style={{
                    transform: settings.voiceOutputEnabled ? 'translateX(20px)' : 'translateX(0)',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
                  }}
                />
              </button>
            </SettingRow>
            <SettingRow label={t('settings.voice.autoplay')} description={t('settings.voice.autoplayDescription')}>
              <button
                onClick={() => { updateSettings({ voiceAutoplay: !settings.voiceAutoplay }); showSaved(); }}
                disabled={!settings.voiceOutputEnabled}
                className="relative w-11 h-6 rounded-full transition-colors cursor-pointer"
                style={{
                  background: settings.voiceAutoplay && settings.voiceOutputEnabled ? 'var(--color-accent)' : 'var(--color-bg-tertiary)',
                  opacity: settings.voiceOutputEnabled ? 1 : 0.4,
                  cursor: settings.voiceOutputEnabled ? 'pointer' : 'default',
                }}
              >
                <span
                  className="absolute top-0.5 left-0.5 w-5 h-5 rounded-full transition-transform bg-white"
                  style={{
                    transform: settings.voiceAutoplay && settings.voiceOutputEnabled ? 'translateX(20px)' : 'translateX(0)',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
                  }}
                />
              </button>
            </SettingRow>
            <WakeWordSettings onSaved={showSaved} />
            <SettingRow label={t('settings.voice.tts')} description={t('settings.voice.ttsDescription')}>
              <div className="flex items-center gap-2">
                <span
                  className="w-2 h-2 rounded-full"
                  style={{
                    background: ttsBackend?.available ? 'var(--color-success)' : 'var(--color-text-tertiary)',
                  }}
                />
                <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                  {ttsBackend === null ? t('settings.voice.checking')
                    : ttsBackend.available ? `${ttsBackend.backend}${ttsBackend.voice_id ? ` / ${ttsBackend.voice_id}` : ''}`
                    : t('settings.voice.notConfigured')}
                </span>
              </div>
            </SettingRow>
            <SettingRow label={t('settings.voice.recognition')} description={t('settings.voice.recognitionDescription')}>
              <div className="flex items-center gap-2">
                <span
                  className="w-2 h-2 rounded-full"
                  style={{
                    background: speechBackendAvailable === true ? 'var(--color-success)'
                      : speechBackendAvailable === false ? 'var(--color-text-tertiary)'
                      : 'var(--color-text-tertiary)',
                  }}
                />
                <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                  {speechBackendAvailable === null ? t('settings.voice.checking')
                    : speechBackendAvailable ? t('settings.voice.available')
                    : t('settings.voice.notConfigured')}
                </span>
              </div>
            </SettingRow>
            {!speechBackendAvailable && speechBackendAvailable !== null && (
              <div className="text-xs mt-2 px-1" style={{ color: 'var(--color-text-tertiary)' }}>
                {t('settings.voice.setupHint')}{' '}
                {t('settings.voice.docsBefore')} <a href="https://github.com/Dracon-46/FalkyriaNicx/blob/main/docs/user-guide/tools.md" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--color-accent)' }}>{t('settings.voice.docsLink')}</a> {t('settings.voice.docsAfter')}
              </div>
            )}
          </Section>

          {/* Atalho de teclado */}
          <Section title={t('settings.shortcut.title')}>
            <ShortcutSettings onSaved={showSaved} />
          </Section>

          {/* Ditado universal: fala e o texto entra onde está o cursor */}
          <Section title={t('settings.dictation.title')}>
            <DictationSettings onSaved={showSaved} />
          </Section>

          {/* Calendário: Windows, Google Agenda ou Outlook */}
          <Section title={t('settings.calendar.title')}>
            <CalendarSettings onSaved={showSaved} />
          </Section>

          {/* Contexto da tela: o que foi copiado e a janela aberta */}
          <Section title={t('settings.context.title')}>
            <ContextSettings onSaved={showSaved} />
          </Section>

          {/* Resumo do dia: o que aconteceu hoje, e o resumo automático */}
          <Section title={t('settings.dailySummary.title')}>
            <DailySummarySettings onSaved={showSaved} />
          </Section>

          {/* Data */}
          <Section title={t('settings.sections.data')}>
            <SettingRow label={t('settings.data.conversations')} description={t('settings.data.storedLocally', { total: conversations.length })}>
              <div className="flex gap-2">
                <button
                  onClick={handleExport}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer"
                  style={{ background: 'var(--color-bg-secondary)', color: 'var(--color-text-secondary)', border: '1px solid var(--color-border)' }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-bg-tertiary)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--color-bg-secondary)')}
                >
                  <Download size={12} /> {t('settings.data.export')}
                </button>
                <button
                  onClick={handleImport}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer"
                  style={{ background: 'var(--color-bg-secondary)', color: 'var(--color-text-secondary)', border: '1px solid var(--color-border)' }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-bg-tertiary)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--color-bg-secondary)')}
                >
                  <Upload size={12} /> {t('settings.data.import')}
                </button>
              </div>
            </SettingRow>
            <SettingRow label={t('settings.data.clearAll')} description={t('settings.data.clearAllDescription')}>
              <button
                onClick={handleClear}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer"
                style={{
                  color: confirmClear ? 'white' : 'var(--color-error)',
                  background: confirmClear ? 'var(--color-error)' : 'transparent',
                  border: '1px solid var(--color-error)',
                }}
                onMouseEnter={(e) => { if (!confirmClear) e.currentTarget.style.background = 'rgba(220,38,38,0.1)'; }}
                onMouseLeave={(e) => { if (!confirmClear) e.currentTarget.style.background = 'transparent'; }}
              >
                <Trash2 size={12} /> {confirmClear ? t('settings.data.confirm') : t('settings.data.clear')}
              </button>
            </SettingRow>
          </Section>

          {/* Privacidade */}
          <PrivacySection />

          {/* About */}
          <Section title={t('settings.sections.about')}>
            <div className="flex items-center gap-4 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              <NicxMascot size="md" interactive className="-mt-4" />
              <div>
                <p className="mb-2">
                  <span className="font-semibold" style={{ color: 'var(--color-text)' }}>Nicx</span> — {t('settings.about.tagline')}
                </p>
                <div className="flex gap-3 mt-3 text-xs">
                  <a
                    href="https://github.com/Dracon-46/FalkyriaNicx"
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: 'var(--color-accent)' }}
                  >
                    {t('settings.about.repository')}
                  </a>
                </div>
              </div>
            </div>
          </Section>
        </div>
      </div>
    </div>
  );
}
