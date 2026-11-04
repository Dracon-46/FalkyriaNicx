import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, Loader2, Pencil, Plus, Sparkles, Trash2, Undo2, Wand2, X } from 'lucide-react';
import {
  ALL_TOOLS,
  apagarAssistente,
  ativarAssistente,
  atualizarAssistente,
  criarAssistente,
  emptyAssistant,
  listarAssistentes,
  proporAssistente,
  toInput,
  type Assistant,
  type AssistantInput,
  type AssistantList,
} from '../lib/assistentes';

const card = {
  background: 'var(--color-bg-secondary)',
  border: '1px solid var(--color-border)',
} as const;
const input = {
  background: 'var(--color-bg)',
  border: '1px solid var(--color-border)',
  color: 'var(--color-text)',
} as const;
const buttonClass =
  'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-default';
const secondaryButton = {
  background: 'var(--color-bg-secondary)',
  color: 'var(--color-text-secondary)',
  border: '1px solid var(--color-border)',
} as const;
const primaryButton = { background: 'var(--color-accent)', color: 'white', border: '1px solid transparent' } as const;
const label = 'block text-xs';
const field = 'mt-1 w-full px-3 py-1.5 rounded-lg text-sm';
/** Acima disto, avisa que as respostas ficam mais lentas (cada token é relido). */
const LONG_INSTRUCTIONS = 800;

type ToolMode = 'none' | 'some' | 'all';

function toolMode(tools: string[]): ToolMode {
  if (tools.includes(ALL_TOOLS)) return 'all';
  return tools.length ? 'some' : 'none';
}

function isAbort(e: unknown): boolean {
  return e instanceof DOMException ? e.name === 'AbortError' : e instanceof Error && e.name === 'AbortError';
}

function ToolsBadge({ tools }: { tools: string[] }) {
  const { t } = useTranslation();
  const mode = toolMode(tools);
  const text =
    mode === 'all'
      ? t('assistentes.mine.allTools')
      : mode === 'none'
        ? t('assistentes.mine.noTools')
        : t('assistentes.mine.tools', { count: tools.length });
  return (
    <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-tertiary)' }}>
      {text}
    </span>
  );
}

interface EditorProps {
  initial: AssistantInput;
  editingId: string | null;
  data: AssistantList;
  onSaved: (a: Assistant) => void;
  onCancel: () => void;
}

function Editor({ initial, editingId, data, onSaved, onCancel }: EditorProps) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState<AssistantInput>(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const limits = data.limites;
  // Próprio estado: "Escolher" com nada marcado ainda é "Escolher".
  const [mode, setModeState] = useState<ToolMode>(toolMode(initial.ferramentas));
  const set = (patch: Partial<AssistantInput>) => setDraft((d) => ({ ...d, ...patch }));
  // Ferramentas do modelo que não estão ligadas neste PC continuam no rascunho
  // (inofensivas), mas só as ligadas aparecem para marcar.
  const available = data.ferramentas;
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    box.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
  }, []);

  const setMode = (next: ToolMode) => {
    setModeState(next);
    if (next === 'all') set({ ferramentas: [ALL_TOOLS] });
    else if (next === 'none') set({ ferramentas: [] });
    else set({ ferramentas: draft.ferramentas.filter((f) => f !== ALL_TOOLS) });
  };

  const toggleTool = (name: string) =>
    set({
      ferramentas: draft.ferramentas.includes(name)
        ? draft.ferramentas.filter((f) => f !== name)
        : [...draft.ferramentas.filter((f) => f !== ALL_TOOLS), name],
    });

  const save = async () => {
    const clean = { ...draft, nome: draft.nome.trim(), instrucoes: draft.instrucoes.trim() };
    if (!clean.nome) return setError(t('assistentes.editor.needName'));
    if (!clean.instrucoes) return setError(t('assistentes.editor.needInstructions'));
    setSaving(true);
    setError('');
    try {
      onSaved(editingId ? await atualizarAssistente(editingId, clean) : await criarAssistente(clean));
    } catch (e) {
      setError(e instanceof Error ? e.message : t('assistentes.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div ref={box} className="rounded-xl p-4 mb-5 space-y-3 scroll-mt-4" style={{ ...card, borderColor: 'var(--color-accent)' }} data-testid="assistant-editor">
      <h2 className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
        {t(editingId ? 'assistentes.editor.editTitle' : 'assistentes.editor.newTitle')}
      </h2>
      <label className={label} style={{ color: 'var(--color-text-secondary)' }}>
        {t('assistentes.editor.name')}
        <input
          value={draft.nome}
          maxLength={limits.nome}
          onChange={(e) => set({ nome: e.target.value })}
          placeholder={t('assistentes.editor.namePlaceholder')}
          className={field}
          style={input}
          data-testid="assistant-name"
        />
      </label>
      <label className={label} style={{ color: 'var(--color-text-secondary)' }}>
        {t('assistentes.editor.description')}
        <input
          value={draft.descricao}
          maxLength={limits.descricao}
          onChange={(e) => set({ descricao: e.target.value })}
          placeholder={t('assistentes.editor.descriptionPlaceholder')}
          className={field}
          style={input}
          data-testid="assistant-description"
        />
      </label>
      <label className={label} style={{ color: 'var(--color-text-secondary)' }}>
        {t('assistentes.editor.instructions')}
        <textarea
          value={draft.instrucoes}
          maxLength={limits.instrucoes}
          onChange={(e) => set({ instrucoes: e.target.value })}
          placeholder={t('assistentes.editor.instructionsPlaceholder')}
          rows={6}
          className={`${field} resize-y`}
          style={input}
          data-testid="assistant-instructions"
        />
        <span className="flex flex-wrap justify-between gap-2 mt-1 text-[11px]" style={{ color: 'var(--color-text-tertiary)' }}>
          <span style={draft.instrucoes.length > LONG_INSTRUCTIONS ? { color: 'var(--color-warning)' } : undefined}>
            {draft.instrucoes.length > LONG_INSTRUCTIONS ? t('assistentes.editor.instructionsLong') : t('assistentes.editor.instructionsHint')}
          </span>
          <span>{t('assistentes.editor.count', { n: draft.instrucoes.length, max: limits.instrucoes })}</span>
        </span>
      </label>
      <label className={label} style={{ color: 'var(--color-text-secondary)' }}>
        {t('assistentes.editor.greeting')}
        <input
          value={draft.saudacao}
          maxLength={limits.saudacao}
          onChange={(e) => set({ saudacao: e.target.value })}
          placeholder={t('assistentes.editor.greetingPlaceholder')}
          className={field}
          style={input}
          data-testid="assistant-greeting"
        />
      </label>

      <fieldset>
        <legend className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          {t('assistentes.editor.tools')}
        </legend>
        <div className="flex flex-wrap gap-3 mt-1 text-xs" style={{ color: 'var(--color-text)' }}>
          {(['none', 'some', 'all'] as const).map((m) => (
            <label key={m} className="flex items-center gap-1.5 cursor-pointer">
              <input type="radio" name="tool-mode" checked={mode === m} onChange={() => setMode(m)} data-testid={`assistant-tools-${m}`} />
              {t(`assistentes.editor.tools_${m}`)}
            </label>
          ))}
        </div>
        {mode === 'some' && (
          <div className="mt-2 grid sm:grid-cols-2 gap-1.5" data-testid="assistant-tool-list">
            {available.length === 0 && (
              <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                {t('assistentes.editor.noToolsAvailable')}
              </p>
            )}
            {available.map((tool) => (
              <label key={tool.nome} className="flex items-start gap-1.5 text-xs cursor-pointer min-w-0" title={tool.descricao}>
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={draft.ferramentas.includes(tool.nome)}
                  onChange={() => toggleTool(tool.nome)}
                  data-testid={`assistant-tool-${tool.nome}`}
                />
                <span className="min-w-0">
                  <span style={{ color: 'var(--color-text)' }}>{tool.nome}</span>
                  <span className="block truncate" style={{ color: 'var(--color-text-tertiary)' }}>
                    {tool.descricao}
                  </span>
                </span>
              </label>
            ))}
          </div>
        )}
        <p className="text-[11px] mt-1" style={{ color: 'var(--color-text-tertiary)' }}>
          {t('assistentes.editor.toolsHint')}
        </p>
      </fieldset>

      <label className="flex items-start gap-2 text-xs cursor-pointer" style={{ color: 'var(--color-text)' }}>
        <input type="checkbox" className="mt-0.5" checked={draft.memoria} onChange={(e) => set({ memoria: e.target.checked })} data-testid="assistant-memory" />
        <span>
          {t('assistentes.editor.memory')}
          <span className="block" style={{ color: 'var(--color-text-tertiary)' }}>
            {t('assistentes.editor.memoryHint')}
          </span>
        </span>
      </label>

      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => void save()} disabled={saving} className={buttonClass} style={primaryButton} data-testid="assistant-save">
          {saving ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
          {t(saving ? 'assistentes.editor.saving' : 'assistentes.editor.save')}
        </button>
        <button type="button" onClick={onCancel} disabled={saving} className={buttonClass} style={secondaryButton} data-testid="assistant-cancel">
          <X size={12} /> {t('assistentes.editor.cancel')}
        </button>
      </div>
      {error && (
        <div className="text-xs" role="alert" style={{ color: 'var(--color-error)' }}>
          {error}
        </div>
      )}
    </div>
  );
}

export function AssistantsPage() {
  const { t, i18n } = useTranslation();
  const [data, setData] = useState<AssistantList | null>(null);
  const [loadError, setLoadError] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [editing, setEditing] = useState<{ initial: AssistantInput; id: string | null; key: number } | null>(null);
  const [description, setDescription] = useState('');
  const [proposing, setProposing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  const editorKey = useRef(0);

  const load = useCallback(async () => {
    try {
      setData(await listarAssistentes(i18n.language));
      setLoadError('');
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : t('assistentes.loadFailed'));
    }
  }, [i18n.language, t]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => () => abort.current?.abort(), []);

  const openEditor = (initial: AssistantInput, id: string | null = null) => {
    editorKey.current += 1;
    setEditing({ initial: toInput(initial), id, key: editorKey.current });
    setNotice('');
    setError('');
  };

  const propose = async () => {
    const text = description.trim();
    if (text.length < 3) return;
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    setProposing(true);
    setError('');
    try {
      openEditor(await proporAssistente(text, i18n.language, controller.signal));
    } catch (e) {
      if (!isAbort(e)) setError(e instanceof Error ? e.message : t('assistentes.proposeFailed'));
    } finally {
      if (abort.current === controller) abort.current = null;
      setProposing(false);
    }
  };

  const activate = async (id: string | null) => {
    setError('');
    try {
      const ativo = await ativarAssistente(id);
      setData((d) => (d ? { ...d, ativo } : d));
    } catch (e) {
      setError(e instanceof Error ? e.message : t('assistentes.activateFailed'));
    }
  };

  const remove = async (id: string) => {
    if (confirmDelete !== id) return setConfirmDelete(id);
    setConfirmDelete(null);
    setError('');
    try {
      await apagarAssistente(id);
      if (editing?.id === id) setEditing(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('assistentes.deleteFailed'));
    }
  };

  const saved = (a: Assistant) => {
    setEditing(null);
    setDescription('');
    setNotice(t('assistentes.editor.saved', { name: a.nome }));
    void load();
  };

  const active = data?.assistentes.find((a) => a.id === data.ativo) ?? null;

  return (
    <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-10">
      <div className="max-w-3xl mx-auto">
        <header className="mb-5">
          <h1 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--color-text)' }}>
            <Sparkles size={18} /> {t('assistentes.title')}
          </h1>
          <p className="text-sm mt-2 max-w-2xl" style={{ color: 'var(--color-text-secondary)' }}>
            {t('assistentes.subtitle')}
          </p>
          <p className="text-xs mt-1 max-w-2xl" style={{ color: 'var(--color-text-tertiary)' }}>
            {t('assistentes.hint')}
          </p>
        </header>

        {loadError && (
          <div className="text-xs mb-4" role="alert" style={{ color: 'var(--color-error)' }}>
            {loadError}
          </div>
        )}
        {!data && !loadError && (
          <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
            <Loader2 size={12} className="animate-spin" /> {t('assistentes.loading')}
          </div>
        )}

        {data && (
          <>
            <div className="rounded-xl px-4 py-3 mb-5 flex flex-wrap items-center justify-between gap-2" style={card} data-testid="assistant-active">
              <span className="text-sm" style={{ color: 'var(--color-text)' }}>
                {active ? t('assistentes.active.talkingTo', { name: active.nome }) : t('assistentes.active.nicx')}
              </span>
              {active && (
                <button type="button" onClick={() => void activate(null)} className={buttonClass} style={secondaryButton} data-testid="assistant-back">
                  <Undo2 size={12} /> {t('assistentes.active.back')}
                </button>
              )}
            </div>

            {editing && (
              <Editor
                key={editing.key}
                initial={editing.initial}
                editingId={editing.id}
                data={data}
                onSaved={saved}
                onCancel={() => setEditing(null)}
              />
            )}
            {notice && (
              <div className="text-xs mb-4" role="status" style={{ color: 'var(--color-success)' }}>
                {notice}
              </div>
            )}
            {error && (
              <div className="text-xs mb-4" role="alert" style={{ color: 'var(--color-error)' }}>
                {error}
              </div>
            )}

            <section className="rounded-xl p-4 mb-5 space-y-2" style={card}>
              <h2 className="text-sm font-semibold flex items-center gap-1.5" style={{ color: 'var(--color-text)' }}>
                <Wand2 size={14} /> {t('assistentes.describe.title')}
              </h2>
              <textarea
                value={description}
                maxLength={500}
                rows={2}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={t('assistentes.describe.placeholder')}
                className="w-full px-3 py-1.5 rounded-lg text-sm resize-y"
                style={input}
                disabled={proposing}
                data-testid="assistant-describe"
              />
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => void propose()}
                  disabled={description.trim().length < 3 || proposing}
                  className={buttonClass}
                  style={primaryButton}
                  data-testid="assistant-propose"
                >
                  {proposing ? <Loader2 size={12} className="animate-spin" /> : <Wand2 size={12} />}
                  {t('assistentes.describe.button')}
                </button>
                <button type="button" onClick={() => openEditor(emptyAssistant())} disabled={proposing} className={buttonClass} style={secondaryButton} data-testid="assistant-new">
                  <Plus size={12} /> {t('assistentes.describe.blank')}
                </button>
                {proposing && (
                  <button type="button" onClick={() => abort.current?.abort()} className={buttonClass} style={secondaryButton} data-testid="assistant-propose-cancel">
                    <X size={12} /> {t('assistentes.describe.cancel')}
                  </button>
                )}
              </div>
              {proposing && (
                <p className="text-xs" role="status" style={{ color: 'var(--color-text-secondary)' }}>
                  {t('assistentes.describe.waiting')}
                </p>
              )}
            </section>

            <section className="mb-5">
              <h2 className="text-sm font-semibold mb-2" style={{ color: 'var(--color-text)' }}>
                {t('assistentes.mine.title')}
              </h2>
              {data.assistentes.length === 0 ? (
                <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }} data-testid="assistant-empty">
                  {t('assistentes.mine.empty')}
                </p>
              ) : (
                <ul className="space-y-2">
                  {data.assistentes.map((a) => {
                    const inUse = a.id === data.ativo;
                    return (
                      <li key={a.id} className="rounded-xl p-3" style={{ ...card, ...(inUse ? { borderColor: 'var(--color-accent)' } : {}) }} data-testid={`assistant-${a.id}`}>
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div className="min-w-0">
                            <div className="text-sm font-semibold break-words" style={{ color: 'var(--color-text)' }}>
                              {a.nome}
                            </div>
                            {a.descricao && (
                              <div className="text-xs mt-0.5 break-words" style={{ color: 'var(--color-text-secondary)' }}>
                                {a.descricao}
                              </div>
                            )}
                            <div className="flex flex-wrap gap-1.5 mt-1.5">
                              <ToolsBadge tools={a.ferramentas} />
                              {!a.memoria && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-tertiary)' }}>
                                  {t('assistentes.mine.noMemory')}
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="flex flex-wrap gap-1.5">
                            <button
                              type="button"
                              onClick={() => void activate(inUse ? null : a.id)}
                              className={buttonClass}
                              style={inUse ? primaryButton : secondaryButton}
                              aria-pressed={inUse}
                              data-testid={`assistant-use-${a.id}`}
                            >
                              {inUse ? <Check size={12} /> : <Sparkles size={12} />}
                              {t(inUse ? 'assistentes.mine.inUse' : 'assistentes.mine.use')}
                            </button>
                            <button type="button" onClick={() => openEditor(a, a.id)} className={buttonClass} style={secondaryButton} data-testid={`assistant-edit-${a.id}`}>
                              <Pencil size={12} /> {t('assistentes.mine.edit')}
                            </button>
                            <button
                              type="button"
                              onClick={() => void remove(a.id)}
                              className={buttonClass}
                              style={confirmDelete === a.id ? { ...secondaryButton, color: 'var(--color-error)', borderColor: 'var(--color-error)' } : secondaryButton}
                              data-testid={`assistant-delete-${a.id}`}
                            >
                              <Trash2 size={12} /> {t(confirmDelete === a.id ? 'assistentes.mine.confirmDelete' : 'assistentes.mine.delete')}
                            </button>
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>

            <section>
              <h2 className="text-sm font-semibold mb-2" style={{ color: 'var(--color-text)' }}>
                {t('assistentes.templates.title')}
              </h2>
              <ul className="grid sm:grid-cols-2 gap-2">
                {data.prontos.map((p) => (
                  <li key={p.id} className="rounded-xl p-3 flex flex-col gap-2" style={card} data-testid={`template-${p.modelo}`}>
                    <div className="min-w-0">
                      <div className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                        {p.nome}
                      </div>
                      <div className="text-xs mt-0.5" style={{ color: 'var(--color-text-secondary)' }}>
                        {p.descricao}
                      </div>
                    </div>
                    <div className="flex items-center justify-between gap-2 mt-auto">
                      <ToolsBadge tools={p.ferramentas} />
                      <button type="button" onClick={() => openEditor(p)} className={buttonClass} style={secondaryButton} data-testid={`template-use-${p.modelo}`}>
                        <Plus size={12} /> {t('assistentes.templates.use')}
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          </>
        )}
      </div>
    </div>
  );
}
