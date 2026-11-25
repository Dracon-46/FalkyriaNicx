import { useCallback, useEffect, useState } from 'react';
import { useLocation } from 'react-router';
import { useTranslation } from 'react-i18next';
import {
  AlertTriangle,
  Briefcase,
  Check,
  CircleDashed,
  FolderOpen,
  Loader2,
  Pause,
  Play,
  Plus,
  Square,
  Trash2,
  Undo2,
  X,
} from 'lucide-react';
import {
  ACTIVE_STATES,
  STARTABLE_STATES,
  acaoTarefa,
  aprovarTarefa,
  criarTarefa,
  escolherPasta,
  listarTarefas,
  responderTarefa,
  verTarefa,
  type Step,
  type Task,
  type TaskState,
} from '../lib/trabalho';

const MAX_STEPS = 7;
const POLL_MS = 1500;

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

const stateColor: Record<TaskState, string> = {
  planejando: 'var(--color-accent)',
  aguardando_aprovacao: 'var(--color-warning)',
  executando: 'var(--color-accent)',
  pausada: 'var(--color-text-secondary)',
  aguardando_confirmacao: 'var(--color-warning)',
  concluida: 'var(--color-success)',
  parada: 'var(--color-text-secondary)',
  erro: 'var(--color-error)',
  desfeita: 'var(--color-text-tertiary)',
  interrompida: 'var(--color-warning)',
};

function folderName(path: string): string {
  const parts = path.split(/[\\/]/).filter(Boolean);
  return parts[parts.length - 1] ?? path;
}

function formatWhen(iso: string, lang: string): string {
  const date = new Date(iso);
  if (!iso || Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(lang, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

function StateBadge({ state }: { state: TaskState }) {
  const { t } = useTranslation();
  return (
    <span
      className="text-[10px] px-1.5 py-0.5 rounded shrink-0"
      style={{ border: `1px solid ${stateColor[state]}`, color: stateColor[state] }}
      data-testid="work-state"
    >
      {t(`trabalho.states.${state}`)}
    </span>
  );
}

function StepIcon({ state }: { state: Step['estado'] }) {
  if (state === 'feito') return <Check size={13} style={{ color: 'var(--color-success)' }} />;
  if (state === 'fazendo') return <Loader2 size={13} className="animate-spin" style={{ color: 'var(--color-accent)' }} />;
  if (state === 'falhou') return <X size={13} style={{ color: 'var(--color-error)' }} />;
  return <CircleDashed size={13} style={{ color: 'var(--color-text-tertiary)' }} />;
}

/** O plano proposto, editável antes de aprovar. */
function PlanEditor({ task, onDone }: { task: Task; onDone: (t: Task) => void }) {
  const { t } = useTranslation();
  const [steps, setSteps] = useState(() => task.plano.map((p) => p.descricao));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const run = async (fn: () => Promise<Task>) => {
    setBusy(true);
    setError('');
    try {
      onDone(await fn());
    } catch (e) {
      setError(e instanceof Error ? e.message : t('trabalho.actionFailed'));
    } finally {
      setBusy(false);
    }
  };

  const clean = steps.map((s) => s.trim());
  const valid = clean.length > 0 && clean.every(Boolean);

  return (
    <div className="space-y-2" data-testid="work-plan-editor">
      <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
        {t('trabalho.plan.hint')}
      </p>
      <ol className="space-y-1.5">
        {steps.map((s, i) => (
          <li
            key={i}
            className="flex items-center gap-1.5 p-2 rounded-lg"
            style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border-subtle)' }}
          >
            <span className="text-xs tabular-nums w-6 shrink-0" style={{ color: 'var(--color-text-tertiary)' }}>
              #{i + 1}
            </span>
            <input
              value={s}
              maxLength={300}
              onChange={(e) => setSteps((list) => list.map((x, j) => (j === i ? e.target.value : x)))}
              aria-label={t('trabalho.plan.step')}
              className="flex-1 min-w-0 px-2 py-1 rounded text-xs"
              style={input}
              data-testid={`work-step-${i}`}
            />
            <button
              type="button"
              onClick={() => setSteps((list) => list.filter((_, j) => j !== i))}
              className="p-1 rounded cursor-pointer"
              style={{ color: 'var(--color-text-tertiary)' }}
              aria-label={t('trabalho.plan.remove')}
            >
              <Trash2 size={12} />
            </button>
          </li>
        ))}
      </ol>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setSteps((list) => (list.length < MAX_STEPS ? [...list, ''] : list))}
          disabled={steps.length >= MAX_STEPS || busy}
          className={buttonClass}
          style={secondaryButton}
        >
          <Plus size={12} /> {t('trabalho.plan.add')}
        </button>
        <button
          type="button"
          onClick={() => void run(() => aprovarTarefa(task.id, clean))}
          disabled={!valid || busy}
          className={buttonClass}
          style={primaryButton}
          data-testid="work-approve"
        >
          <Play size={12} /> {t('trabalho.plan.approve')}
        </button>
        <button
          type="button"
          onClick={() => void run(() => acaoTarefa(task.id, 'parar'))}
          disabled={busy}
          className={buttonClass}
          style={secondaryButton}
        >
          {t('trabalho.plan.discard')}
        </button>
      </div>
      {!valid && steps.length > 0 && (
        <p className="text-xs" style={{ color: 'var(--color-warning)' }}>
          {t('trabalho.plan.emptyStep')}
        </p>
      )}
      {error && (
        <div className="text-xs" role="alert" style={{ color: 'var(--color-error)' }}>
          {error}
        </div>
      )}
    </div>
  );
}

function TaskCard({ task, onChange }: { task: Task; onChange: (t: Task) => void }) {
  const { t, i18n } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [problems, setProblems] = useState<string[]>([]);
  const [showLog, setShowLog] = useState(false);

  const run = async (fn: () => Promise<Task>) => {
    setBusy(true);
    setError('');
    try {
      const next = await fn();
      setProblems(next.problemas ?? []);
      onChange(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('trabalho.actionFailed'));
    } finally {
      setBusy(false);
    }
  };

  const s = task.estado;
  const running = s === 'executando' || s === 'pausada' || s === 'aguardando_confirmacao';
  const canResume = s !== 'aguardando_aprovacao' && STARTABLE_STATES.includes(s) && task.plano.length > 0;
  const canUndo = !ACTIVE_STATES.includes(s) && s !== 'desfeita' && task.arquivos_mudados.length > 0;
  const done = task.plano.filter((p) => p.estado === 'feito').length;

  return (
    <div className="rounded-xl p-4 mb-5 space-y-3" style={card} data-testid="work-task">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-sm font-semibold break-words" style={{ color: 'var(--color-text)' }}>
            {task.pedido}
          </div>
          <div className="text-xs mt-0.5 flex items-center gap-1 break-all" style={{ color: 'var(--color-text-tertiary)' }}>
            <FolderOpen size={11} className="shrink-0" /> {task.pasta}
          </div>
        </div>
        <StateBadge state={s} />
      </div>

      {s === 'planejando' && (
        <p className="text-xs flex items-center gap-1.5" role="status" style={{ color: 'var(--color-text-secondary)' }}>
          <Loader2 size={12} className="animate-spin" /> {t('trabalho.planning')}
        </p>
      )}

      {s === 'aguardando_aprovacao' && <PlanEditor key={task.id} task={task} onDone={onChange} />}

      {s !== 'aguardando_aprovacao' && task.plano.length > 0 && (
        <div>
          <div className="text-xs mb-1.5" style={{ color: 'var(--color-text-secondary)' }}>
            {t('trabalho.progress', { done, total: task.plano.length })}
          </div>
          <ol className="space-y-1">
            {task.plano.map((p, i) => (
              <li key={i} className="flex items-start gap-2 text-xs" data-testid={`work-progress-${i}`}>
                <span className="mt-0.5 shrink-0">
                  <StepIcon state={p.estado} />
                </span>
                <div className="min-w-0">
                  <div style={{ color: 'var(--color-text)' }} className="break-words">
                    {p.descricao}
                  </div>
                  {p.resultado && (
                    <div className="break-words whitespace-pre-wrap" style={{ color: 'var(--color-text-tertiary)' }}>
                      {p.resultado}
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}

      {task.pergunta && (
        <div
          className="rounded-lg p-3 text-xs space-y-2"
          style={{ border: '1px solid var(--color-warning)' }}
          role="alertdialog"
          data-testid="work-question"
        >
          <div className="flex items-start gap-1.5 font-medium" style={{ color: 'var(--color-warning)' }}>
            <AlertTriangle size={13} className="shrink-0 mt-0.5" /> {t('trabalho.question')}
          </div>
          <div className="break-words" style={{ color: 'var(--color-text)' }}>
            {task.pergunta.texto}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => void run(() => responderTarefa(task.id, true))}
              disabled={busy}
              className={buttonClass}
              style={primaryButton}
              data-testid="work-confirm-yes"
            >
              {t('trabalho.yes')}
            </button>
            <button
              type="button"
              onClick={() => void run(() => responderTarefa(task.id, false))}
              disabled={busy}
              className={buttonClass}
              style={secondaryButton}
              data-testid="work-confirm-no"
            >
              {t('trabalho.no')}
            </button>
          </div>
        </div>
      )}

      {task.resumo && (
        <div className="text-sm whitespace-pre-wrap break-words" style={{ color: 'var(--color-text)' }} data-testid="work-summary">
          {task.resumo}
        </div>
      )}
      {task.erro && (
        <div className="text-xs" role="alert" style={{ color: 'var(--color-error)' }}>
          {task.erro}
        </div>
      )}
      {s === 'interrompida' && (
        <p className="text-xs" style={{ color: 'var(--color-warning)' }}>
          {t('trabalho.interrupted')}
        </p>
      )}

      {task.arquivos_mudados.length > 0 && (
        <details className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          <summary className="cursor-pointer">{t('trabalho.changed', { n: task.arquivos_mudados.length })}</summary>
          <ul className="mt-1 list-disc ps-5 break-all">
            {task.arquivos_mudados.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </details>
      )}

      <div className="flex flex-wrap gap-2">
        {s === 'executando' && (
          <button type="button" onClick={() => void run(() => acaoTarefa(task.id, 'pausar'))} disabled={busy} className={buttonClass} style={secondaryButton} data-testid="work-pause">
            <Pause size={12} /> {t('trabalho.pause')}
          </button>
        )}
        {s === 'pausada' && (
          <button type="button" onClick={() => void run(() => acaoTarefa(task.id, 'continuar'))} disabled={busy} className={buttonClass} style={primaryButton} data-testid="work-continue">
            <Play size={12} /> {t('trabalho.continue')}
          </button>
        )}
        {(running || s === 'planejando') && (
          <button type="button" onClick={() => void run(() => acaoTarefa(task.id, 'parar'))} disabled={busy} className={buttonClass} style={secondaryButton} data-testid="work-stop">
            <Square size={12} /> {t('trabalho.stop')}
          </button>
        )}
        {canResume && (
          <button type="button" onClick={() => void run(() => aprovarTarefa(task.id))} disabled={busy} className={buttonClass} style={primaryButton} data-testid="work-resume">
            <Play size={12} /> {t('trabalho.resume')}
          </button>
        )}
        {canUndo && (
          <button type="button" onClick={() => void run(() => acaoTarefa(task.id, 'desfazer'))} disabled={busy} className={buttonClass} style={secondaryButton} data-testid="work-undo">
            <Undo2 size={12} /> {t('trabalho.undo')}
          </button>
        )}
        {(task.registro?.length ?? 0) > 0 && (
          <button type="button" onClick={() => setShowLog((v) => !v)} className={buttonClass} style={secondaryButton}>
            {t(showLog ? 'trabalho.hideLog' : 'trabalho.showLog')}
          </button>
        )}
      </div>
      {s === 'desfeita' && (
        <p className="text-xs" role="status" style={{ color: 'var(--color-success)' }}>
          {t('trabalho.undone')}
        </p>
      )}
      {problems.length > 0 && (
        <ul className="text-xs list-disc ps-5" style={{ color: 'var(--color-warning)' }}>
          {problems.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      )}
      {error && (
        <div className="text-xs" role="alert" style={{ color: 'var(--color-error)' }}>
          {error}
        </div>
      )}
      {showLog && task.registro && (
        <ol
          className="text-[11px] font-mono rounded-lg p-2 max-h-72 overflow-y-auto space-y-0.5"
          style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border-subtle)', color: 'var(--color-text-secondary)' }}
          data-testid="work-log"
        >
          {task.registro.map((r, i) => (
            <li key={i} className="break-words">
              <span style={{ color: 'var(--color-text-tertiary)' }}>{formatWhen(r.quando, i18n.language)}</span> {r.texto}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

export function TrabalhoPage() {
  const { t, i18n } = useTranslation();
  const [folder, setFolder] = useState('');
  const [request, setRequest] = useState('');
  const [creating, setCreating] = useState(false);
  const [picking, setPicking] = useState(false);
  const [error, setError] = useState('');
  const [tasks, setTasks] = useState<Task[]>([]);
  const [current, setCurrent] = useState<Task | null>(null);
  const [loading, setLoading] = useState(true);

  const loadList = useCallback(async () => {
    try {
      setTasks(await listarTarefas());
    } catch (e) {
      setError(e instanceof Error ? e.message : t('trabalho.loadFailed'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  // Veio da caixa de entrada para uma tarefa: abre essa.
  const location = useLocation();
  const requested = (location.state as { tarefa?: string } | null)?.tarefa;
  useEffect(() => {
    if (requested) void verTarefa(requested).then(setCurrent).catch(() => undefined);
  }, [requested]);

  // Abre sozinha a tarefa que está rodando (ex.: voltou para a página).
  useEffect(() => {
    if (current || requested || tasks.length === 0) return;
    const active = tasks.find((x) => ACTIVE_STATES.includes(x.estado) || x.estado === 'aguardando_aprovacao');
    if (active) void verTarefa(active.id).then(setCurrent).catch(() => undefined);
  }, [tasks, current, requested]);

  // Acompanha a tarefa aberta enquanto ela trabalha.
  const currentId = current?.id;
  const watching = current ? ACTIVE_STATES.includes(current.estado) : false;
  useEffect(() => {
    if (!currentId || !watching) return;
    let stop = false;
    const timer = window.setInterval(() => {
      verTarefa(currentId)
        .then((next) => {
          if (stop) return;
          setCurrent(next);
          if (!ACTIVE_STATES.includes(next.estado)) void loadList();
        })
        .catch(() => undefined);
    }, POLL_MS);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
  }, [currentId, watching, loadList]);

  const busyTask = tasks.some((x) => ACTIVE_STATES.includes(x.estado)) || (current ? ACTIVE_STATES.includes(current.estado) : false);

  const pick = async () => {
    setPicking(true);
    setError('');
    try {
      const chosen = await escolherPasta();
      if (chosen) setFolder(chosen);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('trabalho.pickFailed'));
    } finally {
      setPicking(false);
    }
  };

  const create = async () => {
    setCreating(true);
    setError('');
    try {
      const task = await criarTarefa(folder.trim(), request.trim());
      setCurrent(task);
      setRequest('');
      void loadList();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('trabalho.createFailed'));
    } finally {
      setCreating(false);
    }
  };

  const open = async (id: string) => {
    setError('');
    try {
      setCurrent(await verTarefa(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : t('trabalho.loadFailed'));
    }
  };

  const update = (task: Task) => {
    setCurrent(task);
    void loadList();
  };

  const ready = folder.trim().length > 0 && request.trim().length >= 5 && !busyTask;

  return (
    <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-10">
      <div className="max-w-3xl mx-auto">
        <header className="mb-5">
          <h1 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--color-text)' }}>
            <Briefcase size={18} /> {t('trabalho.title')}
          </h1>
          <p className="text-sm mt-2 max-w-2xl" style={{ color: 'var(--color-text-secondary)' }}>
            {t('trabalho.subtitle')}
          </p>
          <p className="text-xs mt-1 max-w-2xl" style={{ color: 'var(--color-text-tertiary)' }}>
            {t('trabalho.hint')}
          </p>
        </header>

        <div className="rounded-xl p-4 mb-5 space-y-3" style={card}>
          <label className="block text-xs" style={{ color: 'var(--color-text-secondary)' }}>
            {t('trabalho.form.folder')}
            <div className="mt-1 flex gap-1.5">
              <input
                value={folder}
                onChange={(e) => setFolder(e.target.value)}
                placeholder={t('trabalho.form.folderPlaceholder')}
                className="flex-1 min-w-0 px-3 py-1.5 rounded-lg text-sm"
                style={input}
                data-testid="work-folder"
              />
              <button type="button" onClick={() => void pick()} disabled={picking} className={buttonClass} style={secondaryButton} data-testid="work-pick">
                {picking ? <Loader2 size={12} className="animate-spin" /> : <FolderOpen size={12} />}
                {t('trabalho.form.pick')}
              </button>
            </div>
          </label>
          <label className="block text-xs" style={{ color: 'var(--color-text-secondary)' }}>
            {t('trabalho.form.request')}
            <textarea
              value={request}
              maxLength={2000}
              rows={3}
              onChange={(e) => setRequest(e.target.value)}
              placeholder={t('trabalho.form.requestPlaceholder')}
              className="mt-1 w-full px-3 py-1.5 rounded-lg text-sm resize-y"
              style={input}
              data-testid="work-request"
            />
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={() => void create()} disabled={!ready || creating} className={buttonClass} style={primaryButton} data-testid="work-create">
              {creating ? <Loader2 size={12} className="animate-spin" /> : <Briefcase size={12} />}
              {t('trabalho.form.create')}
            </button>
            {busyTask && (
              <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                {t('trabalho.form.oneAtATime')}
              </span>
            )}
          </div>
          <p className="text-[11px]" style={{ color: 'var(--color-text-tertiary)' }}>
            {t('trabalho.form.safety')}
          </p>
          {error && (
            <div className="text-sm" role="alert" style={{ color: 'var(--color-error)' }}>
              {error}
            </div>
          )}
        </div>

        {current && <TaskCard key={current.id} task={current} onChange={update} />}

        <h2 className="text-sm font-semibold mb-2" style={{ color: 'var(--color-text)' }}>
          {t('trabalho.list.title')}
        </h2>
        {loading ? (
          <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
            {t('trabalho.loading')}
          </p>
        ) : tasks.length === 0 ? (
          <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }} data-testid="work-empty">
            {t('trabalho.list.empty')}
          </p>
        ) : (
          <ul className="space-y-1.5" data-testid="work-list">
            {tasks.map((x) => (
              <li key={x.id}>
                <button
                  type="button"
                  onClick={() => void open(x.id)}
                  className="w-full text-start rounded-lg px-3 py-2 cursor-pointer"
                  style={{
                    ...card,
                    outline: current?.id === x.id ? '1px solid var(--color-accent)' : undefined,
                  }}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-medium truncate" style={{ color: 'var(--color-text)' }}>
                      {x.pedido}
                    </span>
                    <StateBadge state={x.estado} />
                  </div>
                  <div className="text-[11px] mt-0.5 truncate" style={{ color: 'var(--color-text-tertiary)' }}>
                    {folderName(x.pasta)} · {formatWhen(x.criado_em, i18n.language)}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default TrabalhoPage;
