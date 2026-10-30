import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import { Archive, ArchiveRestore, FolderKanban, GitBranch, Play, Plus, Trash2, X } from 'lucide-react';
import { useAppStore } from '../lib/store';
import {
  addDecision,
  addTask,
  createProject,
  deleteProject,
  deleteTask,
  fetchProjectSignals,
  getProject,
  listProjects,
  setTaskDone,
  updateProject,
  type Project,
  type ProjectList,
  type ProjectSignals,
} from '../lib/projetos-api';

/** "há 5 min", "ontem"... no idioma da interface. */
function relative(iso: string, lang: string): string {
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return '';
  const seconds = (when.getTime() - Date.now()) / 1000;
  const fmt = new Intl.RelativeTimeFormat(lang, { numeric: 'auto' });
  const abs = Math.abs(seconds);
  if (abs < 60) return fmt.format(Math.round(seconds), 'second');
  if (abs < 3600) return fmt.format(Math.round(seconds / 60), 'minute');
  if (abs < 86400) return fmt.format(Math.round(seconds / 3600), 'hour');
  return fmt.format(Math.round(seconds / 86400), 'day');
}

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

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-5">
      <h3 className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--color-text-tertiary)' }}>
        {title}
      </h3>
      {children}
    </section>
  );
}

/** Campo de uma linha + botão "Adicionar" (Enter também envia). */
function AddLine({ label, onAdd, testId }: { label: string; onAdd: (text: string) => Promise<void>; testId: string }) {
  const { t } = useTranslation();
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    const value = text.trim();
    if (!value || busy) return;
    setBusy(true);
    try {
      await onAdd(value);
      setText('');
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex gap-2 mt-2">
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') void submit();
        }}
        placeholder={label}
        aria-label={label}
        data-testid={testId}
        className="flex-1 min-w-0 px-3 py-1.5 rounded-lg text-sm"
        style={input}
      />
      <button type="button" onClick={() => void submit()} disabled={busy || !text.trim()} className={buttonClass} style={secondaryButton}>
        <Plus size={12} /> {t('projects.add')}
      </button>
    </div>
  );
}

function Detail({
  project,
  current,
  onChange,
  onDeleted,
  onError,
}: {
  project: Project;
  current: boolean;
  onChange: (p: Project) => void;
  onDeleted: () => void;
  onError: (message: string) => void;
}) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const selectedModel = useAppStore((s) => s.selectedModel);
  const messages = useAppStore((s) => s.messages);
  const createConversation = useAppStore((s) => s.createConversation);
  const [goal, setGoal] = useState(project.objetivo);
  const [state, setState] = useState(project.estado);
  const [steps, setSteps] = useState(project.proximos_passos.join('\n'));
  const [saved, setSaved] = useState(false);
  const [signals, setSignals] = useState<ProjectSignals | null>(null);

  // Um projeto por montagem (key={id} na página): os campos começam do
  // projeto e não são apagados quando uma pendência muda.
  useEffect(() => {
    let cancelled = false;
    setSignals(null);
    if (project.pastas.length === 0) return;
    fetchProjectSignals(project.id)
      .then((s) => {
        if (!cancelled) setSignals(s);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [project.id, project.pastas]);

  const run = async (action: () => Promise<Project>) => {
    try {
      onChange(await action());
    } catch (e) {
      onError(e instanceof Error ? e.message : t('projects.saveFailed'));
    }
  };

  const dirty =
    goal !== project.objetivo || state !== project.estado || steps !== project.proximos_passos.join('\n');
  const save = async () => {
    await run(() =>
      updateProject(project.id, {
        objetivo: goal,
        estado: state,
        proximos_passos: steps
          .split('\n')
          .map((s) => s.trim())
          .filter(Boolean),
      }),
    );
    setSaved(true);
  };

  const continueHere = () => {
    // Conversa nova: o resumo do projeto cabe com folga no contexto.
    if (messages.length > 0) createConversation(selectedModel);
    navigate('/', { state: { nicxPrompt: t('projects.continuePrompt', { name: project.nome }) } });
  };

  const open = project.pendencias.filter((p) => !p.feita);
  const done = project.pendencias.filter((p) => p.feita).slice(-5).reverse();
  const paths = [...project.pastas, ...project.arquivos];

  return (
    <div className="rounded-xl p-5" style={card} data-testid="project-detail">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-base font-semibold break-words" style={{ color: 'var(--color-text)' }}>
            {project.nome}
          </h2>
          <div className="text-xs mt-1 flex flex-wrap gap-2" style={{ color: 'var(--color-text-tertiary)' }}>
            <span>{t('projects.lastActivity', { when: relative(project.ultima_atividade, i18n.language) })}</span>
            {current && <span style={{ color: 'var(--color-accent)' }}>{t('projects.current')}</span>}
            {project.arquivado && <span>{t('projects.archived')}</span>}
          </div>
        </div>
        <button
          type="button"
          onClick={continueHere}
          className={buttonClass}
          style={{ background: 'var(--color-accent)', color: 'white', border: '1px solid transparent' }}
          data-testid="project-continue"
        >
          <Play size={12} /> {t('projects.continue')}
        </button>
      </div>

      <Section title={t('projects.goal')}>
        <textarea
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          rows={2}
          aria-label={t('projects.goal')}
          className="w-full px-3 py-2 rounded-lg text-sm resize-y"
          style={input}
        />
      </Section>
      <Section title={t('projects.state')}>
        <textarea
          value={state}
          onChange={(e) => setState(e.target.value)}
          rows={2}
          placeholder={t('projects.statePlaceholder')}
          aria-label={t('projects.state')}
          data-testid="project-state"
          className="w-full px-3 py-2 rounded-lg text-sm resize-y"
          style={input}
        />
      </Section>
      <Section title={t('projects.nextSteps')}>
        <textarea
          value={steps}
          onChange={(e) => setSteps(e.target.value)}
          rows={3}
          aria-label={t('projects.nextSteps')}
          className="w-full px-3 py-2 rounded-lg text-sm resize-y"
          style={input}
        />
      </Section>
      <div className="flex items-center gap-2 mt-2">
        <button
          type="button"
          onClick={() => void save()}
          disabled={!dirty}
          className={buttonClass}
          style={secondaryButton}
          data-testid="project-save"
        >
          {t('projects.save')}
        </button>
        {saved && !dirty && (
          <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
            {t('projects.saved')}
          </span>
        )}
      </div>

      <Section title={t('projects.tasks')}>
        {open.length === 0 && (
          <p className="text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
            {t('projects.noTasks')}
          </p>
        )}
        <ul className="space-y-1">
          {[...open, ...done].map((task) => (
            <li key={task.id} className="flex items-center gap-2 text-sm group">
              <input
                type="checkbox"
                checked={task.feita}
                onChange={() => void run(() => setTaskDone(project.id, task.id, !task.feita))}
                aria-label={t(task.feita ? 'projects.markOpen' : 'projects.markDone', { task: task.texto })}
                className="cursor-pointer"
              />
              <span
                className="flex-1 min-w-0 break-words"
                style={{
                  color: task.feita ? 'var(--color-text-tertiary)' : 'var(--color-text)',
                  textDecoration: task.feita ? 'line-through' : 'none',
                }}
              >
                {task.texto}
              </span>
              {task.origem === 'auto' && (
                <span className="text-[10px] px-1.5 rounded" style={{ ...secondaryButton }}>
                  {t('projects.suggested')}
                </span>
              )}
              <button
                type="button"
                onClick={() => void run(() => deleteTask(project.id, task.id))}
                aria-label={t('projects.removeTask')}
                title={t('projects.removeTask')}
                className="opacity-60 hover:opacity-100 cursor-pointer"
                style={{ color: 'var(--color-text-tertiary)' }}
              >
                <X size={12} />
              </button>
            </li>
          ))}
        </ul>
        <AddLine label={t('projects.addTask')} testId="project-add-task" onAdd={(text) => run(() => addTask(project.id, text))} />
      </Section>

      <Section title={t('projects.decisions')}>
        {project.decisoes.length === 0 ? (
          <p className="text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
            {t('projects.noDecisions')}
          </p>
        ) : (
          <ul className="space-y-1">
            {[...project.decisoes].reverse().slice(0, 10).map((d, i) => (
              <li key={`${d.data}-${i}`} className="text-sm flex gap-2" style={{ color: 'var(--color-text)' }}>
                <span className="shrink-0 text-xs pt-0.5" style={{ color: 'var(--color-text-tertiary)' }}>
                  {new Date(d.data).toLocaleDateString(i18n.language)}
                </span>
                <span className="min-w-0 break-words">{d.texto}</span>
                {d.origem === 'auto' && (
                  <span className="text-[10px] px-1.5 rounded self-start" style={{ ...secondaryButton }}>
                    {t('projects.suggested')}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
        <AddLine
          label={t('projects.addDecision')}
          testId="project-add-decision"
          onAdd={(text) => run(() => addDecision(project.id, text))}
        />
      </Section>

      <Section title={t('projects.folders')}>
        {paths.length === 0 ? (
          <p className="text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
            {t('projects.noFolders')}
          </p>
        ) : (
          <ul className="space-y-1">
            {paths.map((path) => (
              <li key={path} className="flex items-center gap-2 text-xs font-mono" style={{ color: 'var(--color-text-secondary)' }}>
                <span className="flex-1 min-w-0 break-all">{path}</span>
                <button
                  type="button"
                  aria-label={t('projects.remove')}
                  title={t('projects.remove')}
                  className="cursor-pointer opacity-60 hover:opacity-100"
                  onClick={() =>
                    void run(() =>
                      updateProject(project.id, {
                        pastas: project.pastas.filter((p) => p !== path),
                        arquivos: project.arquivos.filter((p) => p !== path),
                      }),
                    )
                  }
                >
                  <X size={12} />
                </button>
              </li>
            ))}
          </ul>
        )}
        <AddLine
          label={t('projects.addFolder')}
          testId="project-add-folder"
          onAdd={(text) =>
            run(() =>
              /\.[a-z0-9]{1,6}$/i.test(text)
                ? updateProject(project.id, { arquivos: [...project.arquivos, text] })
                : updateProject(project.id, { pastas: [...project.pastas, text] }),
            )
          }
        />
        {signals?.git && (
          <div className="mt-3 text-xs space-y-0.5" style={{ color: 'var(--color-text-secondary)' }} data-testid="project-git">
            <div className="flex items-center gap-1">
              <GitBranch size={12} /> {t('projects.git', { branch: signals.git.branch || '?' })}
            </div>
            {signals.git.commits[0] && (
              <div className="break-words">
                {t('projects.lastCommit', {
                  subject: signals.git.commits[0].assunto,
                  when: relative(signals.git.commits[0].data, i18n.language),
                })}
              </div>
            )}
            {signals.git.total_alterados > 0 && <div>{t('projects.changed', { n: signals.git.total_alterados })}</div>}
          </div>
        )}
        {signals && signals.recentes.length > 0 && (
          <div className="mt-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
            <div style={{ color: 'var(--color-text-tertiary)' }}>{t('projects.recentFiles')}</div>
            <ul>
              {signals.recentes.map((f) => (
                <li key={f.caminho} className="font-mono break-all">
                  {f.caminho} · {relative(new Date(f.modificado * 1000).toISOString(), i18n.language)}
                </li>
              ))}
            </ul>
          </div>
        )}
      </Section>

      <div className="flex flex-wrap gap-2 mt-6 pt-4" style={{ borderTop: '1px solid var(--color-border-subtle)' }}>
        <button
          type="button"
          onClick={() => void run(() => updateProject(project.id, { arquivado: !project.arquivado }))}
          className={buttonClass}
          style={secondaryButton}
        >
          {project.arquivado ? <ArchiveRestore size={12} /> : <Archive size={12} />}
          {project.arquivado ? t('projects.unarchive') : t('projects.archive')}
        </button>
        <button
          type="button"
          onClick={async () => {
            if (!window.confirm(t('projects.confirmDelete', { name: project.nome }))) return;
            try {
              await deleteProject(project.id);
              onDeleted();
            } catch (e) {
              onError(e instanceof Error ? e.message : t('projects.saveFailed'));
            }
          }}
          className={buttonClass}
          style={{ ...secondaryButton, color: 'var(--color-error)' }}
        >
          <Trash2 size={12} /> {t('projects.delete')}
        </button>
      </div>
    </div>
  );
}

export function ProjectsPage() {
  const { t, i18n } = useTranslation();
  const [list, setList] = useState<ProjectList | null>(null);
  const [selected, setSelected] = useState<Project | null>(null);
  const [archived, setArchived] = useState(false);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState('');
  const [folder, setFolder] = useState('');

  const refresh = useCallback(async () => {
    try {
      const data = await listProjects(archived);
      setList(data);
      setError('');
      return data;
    } catch (e) {
      setError(e instanceof Error ? e.message : t('projects.loadFailed'));
      setList({ projetos: [], atual: null });
      return null;
    }
  }, [archived, t]);

  const select = useCallback(async (id: string) => {
    try {
      setSelected(await getProject(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : t('projects.loadFailed'));
    }
  }, [t]);

  useEffect(() => {
    let cancelled = false;
    void refresh().then((data) => {
      if (cancelled || !data || data.projetos.length === 0) return;
      // Abre o da janela em uso ou o mais recente.
      void select(data.atual ?? data.projetos[0].id);
    });
    return () => {
      cancelled = true;
    };
  }, [refresh, select]);

  const changed = (project: Project) => {
    setSelected(project);
    void refresh();
  };

  const create = async () => {
    const value = name.trim();
    if (!value) return;
    try {
      const project = await createProject(value, '', folder.trim() ? [folder.trim()] : []);
      setName('');
      setFolder('');
      setCreating(false);
      setSelected(project);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('projects.saveFailed'));
    }
  };

  const projects = list?.projetos ?? [];

  return (
    <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-10">
      <div className="max-w-5xl mx-auto">
        <header className="mb-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h1 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--color-text)' }}>
              <FolderKanban size={18} /> {t('projects.title')}
            </h1>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-1.5 text-xs cursor-pointer" style={{ color: 'var(--color-text-secondary)' }}>
                <input type="checkbox" checked={archived} onChange={(e) => setArchived(e.target.checked)} />
                {t('projects.showArchived')}
              </label>
              <button
                type="button"
                onClick={() => setCreating((v) => !v)}
                className={buttonClass}
                style={secondaryButton}
                data-testid="project-new"
              >
                <Plus size={12} /> {t('projects.new')}
              </button>
            </div>
          </div>
          <p className="text-sm mt-2 max-w-2xl" style={{ color: 'var(--color-text-secondary)' }}>
            {t('projects.subtitle')}
          </p>
          <p className="text-xs mt-1 max-w-2xl" style={{ color: 'var(--color-text-tertiary)' }}>
            {t('projects.hint')}
          </p>
        </header>

        {error && (
          <div className="mb-4 text-sm rounded-lg px-3 py-2" role="alert" style={{ ...card, color: 'var(--color-error)' }}>
            {error}
          </div>
        )}

        {creating && (
          <div className="mb-4 rounded-xl p-4 flex flex-col sm:flex-row gap-2" style={card}>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') void create();
              }}
              placeholder={t('projects.namePlaceholder')}
              aria-label={t('projects.name')}
              data-testid="project-name"
              className="flex-1 min-w-0 px-3 py-1.5 rounded-lg text-sm"
              style={input}
            />
            <input
              value={folder}
              onChange={(e) => setFolder(e.target.value)}
              placeholder={t('projects.folderPlaceholder')}
              aria-label={t('projects.folder')}
              className="flex-1 min-w-0 px-3 py-1.5 rounded-lg text-sm font-mono"
              style={input}
            />
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => void create()}
                disabled={!name.trim()}
                className={buttonClass}
                style={{ background: 'var(--color-accent)', color: 'white', border: '1px solid transparent' }}
                data-testid="project-create"
              >
                {t('projects.create')}
              </button>
              <button type="button" onClick={() => setCreating(false)} className={buttonClass} style={secondaryButton}>
                {t('projects.cancel')}
              </button>
            </div>
          </div>
        )}

        {list && projects.length === 0 && !creating ? (
          <p className="text-sm" style={{ color: 'var(--color-text-tertiary)' }} data-testid="projects-empty">
            {t('projects.empty')}
          </p>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-[18rem_1fr] gap-4">
            <ul className="space-y-2" data-testid="projects-list">
              {projects.map((p) => {
                const active = selected?.id === p.id;
                return (
                  <li key={p.id}>
                    <button
                      type="button"
                      onClick={() => void select(p.id)}
                      className="w-full text-left rounded-xl px-4 py-3 cursor-pointer transition-colors"
                      style={{
                        ...card,
                        borderColor: active ? 'var(--color-accent)' : 'var(--color-border)',
                        opacity: p.arquivado ? 0.6 : 1,
                      }}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-medium truncate" style={{ color: 'var(--color-text)' }}>
                          {p.nome}
                        </span>
                        {list?.atual === p.id && (
                          <span className="text-[10px] shrink-0" style={{ color: 'var(--color-accent)' }}>
                            {t('projects.current')}
                          </span>
                        )}
                      </div>
                      <div className="text-xs mt-1 line-clamp-2" style={{ color: 'var(--color-text-secondary)' }}>
                        {p.estado || t('projects.noState')}
                      </div>
                      <div className="text-[11px] mt-1 flex justify-between gap-2" style={{ color: 'var(--color-text-tertiary)' }}>
                        <span>{t('projects.openTasks', { n: p.pendencias_abertas })}</span>
                        <span>{relative(p.ultima_atividade, i18n.language)}</span>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
            <div>
              {selected ? (
                <Detail
                  key={selected.id}
                  project={selected}
                  current={list?.atual === selected.id}
                  onChange={changed}
                  onDeleted={() => {
                    setSelected(null);
                    void refresh();
                  }}
                  onError={setError}
                />
              ) : (
                <p className="text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
                  {t('projects.select')}
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ProjectsPage;
