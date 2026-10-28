import { useState, useRef, useEffect, useCallback } from 'react';
import { Search, Cpu, X, Download, Loader2, Trash2, Check, Cloud, Key, Eye, EyeOff } from 'lucide-react';
import { useAppStore } from '../lib/store';
import {
  pullModel,
  deleteModel,
  fetchModels,
  preloadModel,
  isTauri,
  getCloudKeyStatus,
  saveCloudKey,
} from '../lib/api';
import { useTranslation } from 'react-i18next';

/** Popular models that users can download from the catalogue. */
const CATALOGUE_MODELS = [
  { id: 'qwen3.5:0.8b', size: '~1 GB', desc: 'Qwen 3.5 0.8B', note: 'fastLight' },
  { id: 'qwen3.5:2b', size: '~2.7 GB', desc: 'Qwen 3.5 2B' },
  { id: 'qwen3.5:4b', size: '~3.4 GB', desc: 'Qwen 3.5 4B', note: 'recommended' },
  { id: 'qwen3.5:9b', size: '~6.6 GB', desc: 'Qwen 3.5 9B' },
  { id: 'qwen3.5:27b', size: '~17 GB', desc: 'Qwen 3.5 27B' },
  { id: 'qwen3.5:35b', size: '~24 GB', desc: 'Qwen 3.5 35B' },
  { id: 'qwen3.5:122b', size: '~81 GB', desc: 'Qwen 3.5 122B', note: 'largest' },
  { id: 'llama3.3:latest', size: '~4.9 GB', desc: 'Llama 3.3 8B' },
  { id: 'mistral:latest', size: '~4.1 GB', desc: 'Mistral 7B' },
  { id: 'gemma3:latest', size: '~3.3 GB', desc: 'Gemma 3 4B' },
  { id: 'deepseek-r1:7b', size: '~4.7 GB', desc: 'DeepSeek R1 7B' },
  { id: 'phi4:latest', size: '~9.1 GB', desc: 'Phi-4 14B' },
] as Array<{ id: string; size: string; desc: string; note?: ModelNote }>;

/** Short qualifier shown after a model name (text in common.modelPicker.note). */
type ModelNote =
  | 'fastLight' | 'recommended' | 'largest' | 'fastMultimodal' | 'cheapFast' | 'reasoning'
  | 'balanced' | 'mostCapable' | 'fastest' | 'flagship' | 'fast' | 'latest' | 'auto';

/** Cloud provider definitions */
interface CloudProvider {
  name: string;
  envKey: string;
  models: Array<{ id: string; desc: string; note?: ModelNote }>;
}

const CLOUD_PROVIDERS: CloudProvider[] = [
  {
    name: 'OpenAI',
    envKey: 'OPENAI_API_KEY',
    models: [
      { id: 'gpt-4o', desc: 'GPT-4o', note: 'fastMultimodal' },
      { id: 'gpt-4o-mini', desc: 'GPT-4o Mini', note: 'cheapFast' },
      { id: 'o3-mini', desc: 'o3-mini', note: 'reasoning' },
    ],
  },
  {
    name: 'Anthropic',
    envKey: 'ANTHROPIC_API_KEY',
    models: [
      { id: 'claude-sonnet-4-6', desc: 'Claude Sonnet 4.6', note: 'balanced' },
      { id: 'claude-opus-4-6', desc: 'Claude Opus 4.6', note: 'mostCapable' },
      { id: 'claude-haiku-4-5', desc: 'Claude Haiku 4.5', note: 'fastest' },
    ],
  },
  {
    name: 'Google',
    envKey: 'GEMINI_API_KEY',
    models: [
      { id: 'gemini-2.5-pro', desc: 'Gemini 2.5 Pro', note: 'flagship' },
      { id: 'gemini-2.5-flash', desc: 'Gemini 2.5 Flash', note: 'fast' },
      { id: 'gemini-3-pro', desc: 'Gemini 3 Pro', note: 'latest' },
    ],
  },
  {
    name: 'OpenRouter',
    envKey: 'OPENROUTER_API_KEY',
    models: [
      { id: 'openrouter/auto', desc: 'Auto', note: 'auto' },
      { id: 'openrouter/anthropic/claude-sonnet-4', desc: 'Claude Sonnet 4 via OpenRouter' },
      { id: 'openrouter/deepseek/deepseek-r1', desc: 'DeepSeek R1 via OpenRouter' },
    ],
  },
  {
    name: 'Atlas Cloud',
    envKey: 'ATLASCLOUD_API_KEY',
    models: [
      { id: 'atlascloud/openai/gpt-4.1-mini', desc: 'GPT-4.1 Mini via Atlas Cloud' },
      { id: 'atlascloud/deepseek-ai/deepseek-v3.2', desc: 'DeepSeek V3.2 via Atlas Cloud' },
      { id: 'atlascloud/Qwen/Qwen3-235B-A22B-Instruct-2507', desc: 'Qwen3 235B via Atlas Cloud' },
    ],
  },
];

type Tab = 'installed' | 'catalogue' | 'cloud';

export function CommandPalette() {
  const { t } = useTranslation();
  const describe = (m: { desc: string; note?: ModelNote }) =>
    m.note ? `${m.desc} — ${t(`common.modelPicker.note.${m.note}`)}` : m.desc;
  const [query, setQuery] = useState('');
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [tab, setTab] = useState<Tab>('installed');
  const [pulling, setPulling] = useState<string | null>(null);
  const [pullError, setPullError] = useState<string | null>(null);
  const [pullSuccess, setPullSuccess] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [customModel, setCustomModel] = useState('');
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [cloudKeyStatus, setCloudKeyStatus] = useState<Record<string, boolean>>({});
  const [cloudKeyError, setCloudKeyError] = useState<string | null>(null);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const models = useAppStore((s) => s.models);
  const selectedModel = useAppStore((s) => s.selectedModel);
  const setSelectedModel = useAppStore((s) => s.setSelectedModel);
  const setModels = useAppStore((s) => s.setModels);
  const setCommandPaletteOpen = useAppStore((s) => s.setCommandPaletteOpen);

  const installedIds = new Set(models.map((m) => m.id));
  const desktopKeyStorage = isTauri();

  const refreshCloudKeyStatus = useCallback(async () => {
    if (!desktopKeyStorage) {
      setCloudKeyStatus({});
      return;
    }
    try {
      setCloudKeyStatus(await getCloudKeyStatus());
      setCloudKeyError(null);
    } catch (e: any) {
      setCloudKeyError(e?.message || t('common.modelPicker.keyStatusFailed'));
    }
  }, [desktopKeyStorage, t]);

  const filtered = tab === 'installed'
    ? (query
        ? models.filter((m) => m.id.toLowerCase().includes(query.toLowerCase()))
        : models)
    : tab === 'catalogue'
    ? CATALOGUE_MODELS.filter((m) =>
        !installedIds.has(m.id) &&
        (!query || m.id.toLowerCase().includes(query.toLowerCase()) || describe(m).toLowerCase().includes(query.toLowerCase()))
      )
    : []; // cloud tab doesn't use filtered

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    void refreshCloudKeyStatus();
  }, [refreshCloudKeyStatus]);

  useEffect(() => {
    setSelectedIdx(0);
  }, [query, tab]);

  useEffect(() => {
    if (pullSuccess) {
      const timer = setTimeout(() => setPullSuccess(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [pullSuccess]);

  const handleSelect = async (modelId: string, owner?: string) => {
    const previousModel = selectedModel;
    setSelectedModel(modelId);
    setCommandPaletteOpen(false);

    if (modelId !== previousModel) {
      const { setModelLoading, addLogEntry } = useAppStore.getState();
      setModelLoading(true);
      addLogEntry({ timestamp: Date.now(), level: 'info', category: 'model', message: t('common.modelPicker.log.switching', { model: modelId }) });
      try {
        await preloadModel(modelId, owner);
        addLogEntry({ timestamp: Date.now(), level: 'info', category: 'model', message: t('common.modelPicker.log.loaded', { model: modelId }) });
      } catch (e: any) {
        addLogEntry({ timestamp: Date.now(), level: 'error', category: 'model', message: t('common.modelPicker.log.loadFailed', { model: modelId, message: e.message }) });
      } finally {
        setModelLoading(false);
      }
    }
  };

  const refreshModels = async () => {
    try {
      const m = await fetchModels();
      setModels(m);
    } catch {}
  };

  const handlePull = async (modelId: string) => {
    setPulling(modelId);
    setPullError(null);
    try {
      await pullModel(modelId);
      setPullSuccess(modelId);
      useAppStore.getState().addLogEntry({
        timestamp: Date.now(), level: 'info', category: 'model',
        message: t('common.modelPicker.log.downloaded', { model: modelId }),
      });
      await refreshModels();
      setSelectedModel(modelId);
    } catch (e: any) {
      setPullError(e.message || t('common.modelPicker.downloadFailed'));
      useAppStore.getState().addLogEntry({
        timestamp: Date.now(), level: 'error', category: 'model',
        message: t('common.modelPicker.log.downloadFailed', { model: modelId, message: e.message }),
      });
    } finally {
      setPulling(null);
    }
  };

  const handleDelete = async (modelId: string) => {
    setDeleting(modelId);
    try {
      await deleteModel(modelId);
      useAppStore.getState().addLogEntry({
        timestamp: Date.now(), level: 'info', category: 'model',
        message: t('common.modelPicker.log.deleted', { model: modelId }),
      });
      await refreshModels();
      if (selectedModel === modelId) {
        const remaining = models.filter((m) => m.id !== modelId);
        if (remaining.length > 0) setSelectedModel(remaining[0].id);
      }
    } catch {} finally {
      setDeleting(null);
    }
  };

  const handleCustomPull = async () => {
    const name = customModel.trim();
    if (!name) return;
    await handlePull(name);
    setCustomModel('');
  };

  const handleSaveKey = async (provider: CloudProvider, value: string) => {
    const keyValue = value.trim();
    setSavingKey(provider.envKey);
    setCloudKeyError(null);

    try {
      await saveCloudKey(provider.envKey, keyValue);
      setApiKeys((prev) => ({ ...prev, [provider.envKey]: '' }));
      await refreshCloudKeyStatus();
      useAppStore.getState().addLogEntry({
        timestamp: Date.now(), level: 'info', category: 'model',
        message: t(keyValue ? 'common.modelPicker.log.keySaved' : 'common.modelPicker.log.keyRemoved', { provider: provider.name }),
      });
      await refreshModels();
    } catch (e: any) {
      setCloudKeyError(e?.message || t('common.modelPicker.keySaveFailed', { provider: provider.name }));
    } finally {
      setSavingKey(null);
    }
  };

  const handleKeyBlur = (provider: CloudProvider) => {
    const draft = apiKeys[provider.envKey] || '';
    if (draft.trim()) void handleSaveKey(provider, draft);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setCommandPaletteOpen(false);
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIdx((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIdx((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && tab === 'installed' && filtered.length > 0) {
      e.preventDefault();
      const model = filtered[selectedIdx] as (typeof models)[number];
      handleSelect(model.id, model.owned_by);
    }
  };

  const TAB_LABELS: Record<Tab, string> = {
    installed: t('common.modelPicker.tabInstalled', { n: models.length }),
    catalogue: t('common.modelPicker.tabDownload'),
    cloud: t('common.modelPicker.tabCloud'),
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]"
      onClick={() => setCommandPaletteOpen(false)}
    >
      <div className="fixed inset-0" style={{ background: 'rgba(0,0,0,0.5)' }} />

      <div
        className="relative w-full max-w-lg rounded-xl overflow-hidden"
        style={{
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          boxShadow: 'var(--shadow-lg)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Tabs */}
        <div className="flex" style={{ borderBottom: '1px solid var(--color-border)' }}>
          {(['installed', 'catalogue', 'cloud'] as Tab[]).map((id) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className="flex-1 px-3 py-2.5 text-xs font-medium transition-colors cursor-pointer"
              style={{
                color: tab === id ? 'var(--color-accent)' : 'var(--color-text-tertiary)',
                borderBottom: tab === id ? '2px solid var(--color-accent)' : '2px solid transparent',
                background: 'transparent',
              }}
            >
              {TAB_LABELS[id]}
            </button>
          ))}
        </div>

        {/* Search (not for cloud tab) */}
        {tab !== 'cloud' && (
          <div
            className="flex items-center gap-3 px-4 py-3"
            style={{ borderBottom: '1px solid var(--color-border)' }}
          >
            <Search size={18} style={{ color: 'var(--color-text-tertiary)' }} />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={tab === 'installed' ? t('common.modelPicker.searchInstalled') : t('common.modelPicker.searchDownload')}
              className="flex-1 bg-transparent outline-none text-sm"
              style={{ color: 'var(--color-text)' }}
            />
            <button
              onClick={() => setCommandPaletteOpen(false)}
              aria-label={t('common.close')}
              title={t('common.close')}
              className="p-1 rounded cursor-pointer"
              style={{ color: 'var(--color-text-tertiary)' }}
            >
              <X size={16} />
            </button>
          </div>
        )}

        {/* Status messages */}
        {pullError && (
          <div className="px-4 py-2 text-xs" style={{ color: 'var(--color-error)', background: 'rgba(220,38,38,0.05)' }}>
            {pullError}
          </div>
        )}
        {pullSuccess && (
          <div className="px-4 py-2 text-xs flex items-center gap-1.5" style={{ color: 'var(--color-success)', background: 'color-mix(in srgb, var(--color-success) 5%, transparent)' }}>
            <Check size={12} /> {t('common.modelPicker.downloadedOk', { model: pullSuccess })}
          </div>
        )}
        {tab === 'cloud' && cloudKeyError && (
          <div className="px-4 py-2 text-xs" style={{ color: 'var(--color-error)', background: 'rgba(220,38,38,0.05)' }}>
            {cloudKeyError}
          </div>
        )}

        {/* Results */}
        <div className="max-h-[400px] overflow-y-auto py-2">
          {tab === 'installed' ? (
            filtered.length === 0 ? (
              <div className="px-4 py-6 text-center text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
                {models.length === 0
                  ? t('common.modelPicker.noModels')
                  : t('common.modelPicker.noMatches')}
              </div>
            ) : (
              (filtered as typeof models).map((model, idx) => {
                const isActive = model.id === selectedModel;
                const isSelected = idx === selectedIdx;
                const isDeleting = deleting === model.id;
                return (
                  <div
                    key={model.id}
                    className="flex items-center gap-3 w-full px-4 py-2.5 transition-colors"
                    style={{ background: isSelected ? 'var(--color-bg-secondary)' : 'transparent' }}
                    onMouseEnter={() => setSelectedIdx(idx)}
                  >
                    <button
                      onClick={() => handleSelect(model.id, model.owned_by)}
                      className="flex items-center gap-3 flex-1 min-w-0 text-left cursor-pointer"
                      style={{ background: 'none', border: 'none', padding: 0 }}
                    >
                      {model.owned_by === 'litellm' ? (
                        <Cloud size={16} style={{ color: isActive ? 'var(--color-accent)' : 'var(--color-text-tertiary)' }} />
                      ) : (
                        <Cpu size={16} style={{ color: isActive ? 'var(--color-accent)' : 'var(--color-text-tertiary)' }} />
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="text-sm truncate" style={{ color: isActive ? 'var(--color-accent)' : 'var(--color-text)', fontWeight: isActive ? 500 : 400 }}>
                          {model.id}
                        </div>
                      </div>
                      {isActive && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: 'var(--color-accent-subtle)', color: 'var(--color-accent)' }}>
                          {t('common.modelPicker.active')}
                        </span>
                      )}
                    </button>
                    {model.owned_by !== 'litellm' && (
                      <button
                        onClick={() => handleDelete(model.id)}
                        disabled={isDeleting}
                        className="p-1 rounded transition-colors cursor-pointer"
                        style={{ color: 'var(--color-text-tertiary)', opacity: 0 }}
                        title={t('common.modelPicker.deleteModel')}
                        aria-label={t('common.modelPicker.deleteModel')}
                        onMouseEnter={(e) => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.color = 'var(--color-error)'; }}
                        onMouseLeave={(e) => { e.currentTarget.style.opacity = '0'; e.currentTarget.style.color = 'var(--color-text-tertiary)'; }}
                      >
                        {isDeleting ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                      </button>
                    )}
                  </div>
                );
              })
            )
          ) : tab === 'catalogue' ? (
            <>
              {(filtered as typeof CATALOGUE_MODELS).map((model) => {
                const isPulling = pulling === model.id;
                const justInstalled = pullSuccess === model.id;
                return (
                  <div key={model.id} className="flex items-center gap-3 w-full px-4 py-2.5">
                    <Download size={16} style={{ color: 'var(--color-text-tertiary)' }} />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm truncate" style={{ color: 'var(--color-text)' }}>{model.id}</div>
                      <div className="text-[11px]" style={{ color: 'var(--color-text-tertiary)' }}>{describe(model)} &middot; {model.size}</div>
                    </div>
                    <button
                      onClick={() => handlePull(model.id)}
                      disabled={isPulling || !!pulling}
                      className="flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium cursor-pointer"
                      style={{
                        background: justInstalled ? 'var(--color-accent-subtle)' : 'var(--color-accent)',
                        color: justInstalled ? 'var(--color-accent)' : 'var(--color-on-accent)',
                        opacity: (isPulling || (pulling && !isPulling)) ? 0.5 : 1,
                      }}
                    >
                      {isPulling ? <><Loader2 size={12} className="animate-spin" /> {t('common.modelPicker.downloading')}</> :
                       justInstalled ? <><Check size={12} /> {t('common.modelPicker.installed')}</> :
                       <><Download size={12} /> {t('common.modelPicker.download')}</>}
                    </button>
                  </div>
                );
              })}
              <div className="px-4 py-3 mt-1" style={{ borderTop: '1px solid var(--color-border)' }}>
                <div className="text-[11px] mb-2" style={{ color: 'var(--color-text-tertiary)' }}>{t('common.modelPicker.customLabel')}</div>
                <div className="flex gap-2">
                  <input
                    type="text" value={customModel}
                    onChange={(e) => setCustomModel(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleCustomPull(); } }}
                    placeholder={t('common.modelPicker.customPlaceholder')}
                    className="flex-1 text-sm px-3 py-1.5 rounded-lg outline-none"
                    style={{ background: 'var(--color-bg-secondary)', color: 'var(--color-text)', border: '1px solid var(--color-border)' }}
                  />
                  <button
                    onClick={handleCustomPull} disabled={!customModel.trim() || !!pulling}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer"
                    style={{ background: 'var(--color-accent)', color: 'var(--color-on-accent)', opacity: (!customModel.trim() || pulling) ? 0.5 : 1 }}
                  >
                    <Download size={12} /> {t('common.modelPicker.pull')}
                  </button>
                </div>
              </div>
            </>
          ) : (
            /* ── Cloud Models tab ── */
            <div className="px-4 py-2">
              <div className="text-[11px] mb-3" style={{ color: 'var(--color-text-tertiary)' }}>
                {desktopKeyStorage
                  ? t('common.modelPicker.cloudDesktopHint')
                  : t('common.modelPicker.cloudServerHint')}
              </div>

              {CLOUD_PROVIDERS.map((provider) => {
                const key = apiKeys[provider.envKey] || '';
                const hasSavedKey = !!cloudKeyStatus[provider.envKey];
                const hasKey = hasSavedKey || !!key.trim();
                const isVisible = showKeys[provider.envKey];
                const isSaving = savingKey === provider.envKey;

                return (
                  <div key={provider.name} className="mb-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Cloud size={14} style={{ color: hasKey ? 'var(--color-success)' : 'var(--color-text-tertiary)' }} />
                      <span className="text-xs font-medium" style={{ color: 'var(--color-text)' }}>{provider.name}</span>
                      {hasKey && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ background: 'color-mix(in srgb, var(--color-success) 10%, transparent)', color: 'var(--color-success)' }}>
                          {t('common.modelPicker.connected')}
                        </span>
                      )}
                    </div>

                    {/* API key input */}
                    <div className="flex gap-1.5 mb-2">
                      <div className="flex-1 flex items-center rounded-lg" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
                        <Key size={12} className="ml-2.5 shrink-0" style={{ color: 'var(--color-text-tertiary)' }} />
                        <input
                          type={isVisible ? 'text' : 'password'}
                          value={key}
                          onChange={(e) => setApiKeys((prev) => ({ ...prev, [provider.envKey]: e.target.value }))}
                          onBlur={() => handleKeyBlur(provider)}
                          placeholder={hasSavedKey ? t('common.modelPicker.keySaved') : provider.envKey}
                          disabled={!desktopKeyStorage || isSaving}
                          className="flex-1 text-xs px-2 py-1.5 bg-transparent outline-none font-mono"
                          style={{ color: 'var(--color-text)' }}
                        />
                        <button
                          onClick={() => setShowKeys((prev) => ({ ...prev, [provider.envKey]: !prev[provider.envKey] }))}
                          className="px-2 cursor-pointer" style={{ color: 'var(--color-text-tertiary)' }}
                          aria-label={isVisible ? t('common.modelPicker.hideKey') : t('common.modelPicker.showKey')}
                          title={isVisible ? t('common.modelPicker.hideKey') : t('common.modelPicker.showKey')}
                        >
                          {isVisible ? <EyeOff size={12} /> : <Eye size={12} />}
                        </button>
                      </div>
                      {hasSavedKey && (
                        <button
                          onClick={() => handleSaveKey(provider, '')}
                          disabled={isSaving}
                          className="px-2 py-1 rounded-lg text-[10px] cursor-pointer"
                          style={{ color: 'var(--color-error)', border: '1px solid var(--color-error)', opacity: isSaving ? 0.5 : 1 }}
                        >
                          {isSaving ? t('common.modelPicker.saving') : t('common.modelPicker.remove')}
                        </button>
                      )}
                    </div>

                    {/* Models for this provider (only show if key is set) */}
                    {hasKey && (
                      <div className="ml-5 flex flex-col gap-1">
                        {provider.models.map((model) => {
                          const isActive = model.id === selectedModel;
                          return (
                            <button
                              key={model.id}
                              onClick={() => handleSelect(model.id)}
                              className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-left cursor-pointer transition-colors"
                              style={{ background: isActive ? 'var(--color-accent-subtle)' : 'transparent' }}
                              onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.background = 'var(--color-bg-secondary)'; }}
                              onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
                            >
                              <Cloud size={12} style={{ color: isActive ? 'var(--color-accent)' : 'var(--color-text-tertiary)' }} />
                              <div className="flex-1 min-w-0">
                                <div className="text-xs truncate" style={{ color: isActive ? 'var(--color-accent)' : 'var(--color-text)', fontWeight: isActive ? 500 : 400 }}>
                                  {model.id}
                                </div>
                                <div className="text-[10px] truncate" style={{ color: 'var(--color-text-tertiary)' }}>
                                  {describe(model)}
                                </div>
                              </div>
                              {isActive && (
                                <span className="text-[9px] px-1.5 py-0.5 rounded-full shrink-0" style={{ background: 'var(--color-accent-subtle)', color: 'var(--color-accent)' }}>
                                  {t('common.modelPicker.active')}
                                </span>
                              )}
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          className="flex items-center gap-4 px-4 py-2 text-[11px]"
          style={{ borderTop: '1px solid var(--color-border)', color: 'var(--color-text-tertiary)' }}
        >
          {tab === 'installed' ? (
            <>
              <span><kbd className="font-mono">↑↓</kbd> {t('common.modelPicker.navigate')}</span>
              <span><kbd className="font-mono">Enter</kbd> {t('common.modelPicker.select')}</span>
              <span><kbd className="font-mono">Esc</kbd> {t('common.close')}</span>
            </>
          ) : tab === 'catalogue' ? (
            <span>{t('common.modelPicker.catalogueFooter')}</span>
          ) : (
            <span>{t('common.modelPicker.cloudFooter')}</span>
          )}
        </div>
      </div>
    </div>
  );
}
