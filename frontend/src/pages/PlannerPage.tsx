import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, CalendarClock, ExternalLink, Loader2, Plus, RefreshCw, Target, Trash2, X } from 'lucide-react';
import { listProjects } from '../lib/projetos-api';
import {
  criarPlano,
  interpretarPrazo,
  obterProgresso,
  proporEtapas,
  reajustarPlano,
  type CreatedPlan,
  type PlanProgress,
  type ProposedStep,
} from '../lib/planejador';

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
const field = 'px-2 py-1 rounded text-xs min-w-0';

/** AAAA-MM-DD local. */
function isoDay(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function tomorrow(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return isoDay(d);
}

function formatDay(iso: string, lang: string): string {
  const [y, m, d] = iso.split('-').map(Number);
  const date = new Date(y, (m ?? 1) - 1, d ?? 1);
  if (!iso || Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(lang, { day: 'numeric', month: 'short', year: 'numeric' });
}

function isAbort(e: unknown): boolean {
  return e instanceof DOMException ? e.name === 'AbortError' : e instanceof Error && e.name === 'AbortError';
}

/** Remove a etapa `index` e ajusta as dependências das outras. */
function removeStep(steps: ProposedStep[], index: number): ProposedStep[] {
  return steps
    .filter((_, i) => i !== index)
    .map((s) => ({ ...s, depende_de: s.depende_de.filter((d) => d !== index).map((d) => (d > index ? d - 1 : d)) }));
}

function PlanCard({ plan, onChange }: { plan: PlanProgress; onChange: (p: PlanProgress) => void }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [newDeadline, setNewDeadline] = useState('');
  const [adjusting, setAdjusting] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);

  const days = plan.dias_restantes;
  const remaining =
    days === null
      ? ''
      : days < 0
        ? t('planejador.plans.overdue')
        : days === 0
          ? t('planejador.plans.dueToday')
          : t('planejador.plans.daysLeft', { n: days });
  const late = plan.atrasadas.length > 0;
  const pct = Math.max(0, Math.min(100, plan.percentual));

  const adjust = async () => {
    setAdjusting(true);
    setError('');
    setDone(false);
    try {
      onChange(await reajustarPlano(plan.projeto, newDeadline || undefined));
      setNewDeadline('');
      setDone(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('planejador.adjustFailed'));
    } finally {
      setAdjusting(false);
    }
  };

  return (
    <li className="rounded-xl p-4" style={card} data-testid={`plan-${plan.projeto}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-sm font-semibold break-words" style={{ color: 'var(--color-text)' }}>
            {plan.nome}
          </div>
          <div className="text-xs mt-0.5 flex items-center gap-1" style={{ color: 'var(--color-text-tertiary)' }}>
            <CalendarClock size={11} />
            {t('planejador.plans.deadline', { date: formatDay(plan.prazo, i18n.language) })}
            {remaining && ` · ${remaining}`}
          </div>
        </div>
        <span
          className="text-[10px] px-1.5 py-0.5 rounded shrink-0"
          style={{
            border: `1px solid ${plan.no_ritmo ? 'var(--color-success)' : 'var(--color-warning)'}`,
            color: plan.no_ritmo ? 'var(--color-success)' : 'var(--color-warning)',
          }}
          data-testid={`plan-pace-${plan.projeto}`}
        >
          {t(plan.no_ritmo ? 'planejador.plans.onTrack' : 'planejador.plans.behind')}
        </span>
      </div>

      <div className="mt-3">
        <div
          className="h-2 rounded-full overflow-hidden"
          style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border-subtle)' }}
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct}
          aria-label={t('planejador.plans.progress')}
        >
          <div className="h-full" style={{ width: `${pct}%`, background: 'var(--color-accent)' }} />
        </div>
        <div className="text-xs mt-1" style={{ color: 'var(--color-text-secondary)' }} data-testid={`plan-progress-${plan.projeto}`}>
          {t('planejador.plans.stepsDone', { done: plan.feitas, total: plan.total, pct })}
        </div>
      </div>

      {plan.proxima && (
        <div className="text-xs mt-2" style={{ color: 'var(--color-text-secondary)' }}>
          {t('planejador.plans.next', { step: plan.proxima.texto, date: formatDay(plan.proxima.prazo, i18n.language) })}
        </div>
      )}
      {!plan.proxima && plan.total > 0 && plan.feitas === plan.total && (
        <div className="text-xs mt-2" style={{ color: 'var(--color-success)' }}>
          {t('planejador.plans.allDone')}
        </div>
      )}

      {late && (
        <div className="mt-2 text-xs rounded-lg px-2.5 py-1.5" style={{ border: '1px solid var(--color-warning)', color: 'var(--color-warning)' }} data-testid={`plan-late-${plan.projeto}`}>
          <div className="flex items-center gap-1 font-medium">
            <AlertTriangle size={12} /> {t('planejador.plans.late', { n: plan.atrasadas.length })}
          </div>
          <ul className="mt-1 list-disc ps-5">
            {plan.atrasadas.slice(0, 5).map((a) => (
              <li key={a.id} className="break-words">
                {a.texto} ({formatDay(a.prazo, i18n.language)})
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          {t('planejador.plans.newDeadline')}
          <input
            type="date"
            value={newDeadline}
            min={tomorrow()}
            onChange={(e) => setNewDeadline(e.target.value)}
            className={field}
            style={input}
            data-testid={`plan-deadline-${plan.projeto}`}
          />
        </label>
        <button
          type="button"
          onClick={() => void adjust()}
          disabled={adjusting}
          className={buttonClass}
          style={secondaryButton}
          data-testid={`plan-adjust-${plan.projeto}`}
        >
          <RefreshCw size={12} /> {adjusting ? t('planejador.plans.adjusting') : t('planejador.plans.adjust')}
        </button>
        <button
          type="button"
          onClick={() => navigate('/projetos', { state: { projeto: plan.projeto } })}
          className={buttonClass}
          style={secondaryButton}
          data-testid={`plan-open-${plan.projeto}`}
        >
          <ExternalLink size={12} /> {t('planejador.plans.openProject')}
        </button>
      </div>
      <p className="text-[11px] mt-1" style={{ color: 'var(--color-text-tertiary)' }}>
        {t('planejador.plans.adjustHint')}
      </p>
      {done && (
        <div className="text-xs mt-1" role="status" style={{ color: 'var(--color-success)' }}>
          {t('planejador.plans.adjusted')}
        </div>
      )}
      {error && (
        <div className="text-xs mt-1" role="alert" style={{ color: 'var(--color-error)' }}>
          {error}
        </div>
      )}
    </li>
  );
}

export function PlannerPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [goal, setGoal] = useState('');
  const [deadline, setDeadline] = useState('');
  const [deadlineText, setDeadlineText] = useState('');
  const [name, setName] = useState('');
  const [steps, setSteps] = useState<ProposedStep[] | null>(null);
  const [proposing, setProposing] = useState(false);
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<CreatedPlan | null>(null);
  const [error, setError] = useState('');
  const [plans, setPlans] = useState<PlanProgress[]>([]);
  const [loadingPlans, setLoadingPlans] = useState(true);
  const [plansError, setPlansError] = useState('');
  const abort = useRef<AbortController | null>(null);

  const loadPlans = useCallback(async () => {
    try {
      const list = await listProjects();
      const all = await Promise.all(list.projetos.map((p) => obterProgresso(p.id).catch(() => null)));
      setPlans(all.filter((p): p is PlanProgress => Boolean(p?.prazo)));
      setPlansError('');
    } catch (e) {
      setPlansError(e instanceof Error ? e.message : t('planejador.loadFailed'));
    } finally {
      setLoadingPlans(false);
    }
  }, [t]);

  useEffect(() => {
    void loadPlans();
  }, [loadPlans]);

  // Sai da página no meio da proposta: para de esperar.
  useEffect(() => () => abort.current?.abort(), []);

  const resolveDeadline = async () => {
    const texto = deadlineText.trim();
    if (!texto) return;
    setError('');
    try {
      const prazo = await interpretarPrazo(texto);
      if (prazo) {
        setDeadline(prazo);
        setDeadlineText('');
      } else setError(t('planejador.form.deadlineUnknown'));
    } catch (e) {
      setError(e instanceof Error ? e.message : t('planejador.deadlineFailed'));
    }
  };

  const ready = goal.trim().length >= 3 && Boolean(deadline);

  const propose = async () => {
    if (!ready) return;
    const controller = new AbortController();
    abort.current = controller;
    setProposing(true);
    setError('');
    setCreated(null);
    try {
      const proposal = await proporEtapas(goal.trim(), deadline, i18n.language, controller.signal);
      setSteps(proposal.etapas);
      if (proposal.prazo) setDeadline(proposal.prazo);
    } catch (e) {
      if (!isAbort(e)) setError(e instanceof Error ? e.message : t('planejador.proposeFailed'));
    } finally {
      if (abort.current === controller) abort.current = null;
      setProposing(false);
    }
  };

  const cancel = () => abort.current?.abort();

  const setStep = (i: number, patch: Partial<ProposedStep>) =>
    setSteps((list) => (list ? list.map((s, j) => (j === i ? { ...s, ...patch } : s)) : list));

  const create = async () => {
    if (!steps) return;
    const etapas = steps
      .map((s) => ({ ...s, texto: s.texto.trim(), minutos: Math.max(15, Math.round(s.minutos || 60)) }))
      .filter((s) => s.texto);
    if (etapas.length === 0) return setError(t('planejador.form.needStep'));
    if (etapas.length !== steps.length) return setError(t('planejador.form.emptyStep'));
    setCreating(true);
    setError('');
    try {
      const result = await criarPlano({
        objetivo: goal.trim(),
        prazo: deadline,
        etapas,
        nome: name.trim() || undefined,
        idioma: i18n.language,
      });
      setCreated(result);
      setSteps(null);
      setGoal('');
      setName('');
      setDeadline('');
      void loadPlans();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('planejador.createFailed'));
    } finally {
      setCreating(false);
    }
  };

  const totalMinutes = steps?.reduce((sum, s) => sum + (s.minutos || 0), 0) ?? 0;

  return (
    <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-10">
      <div className="max-w-3xl mx-auto">
        <header className="mb-5">
          <h1 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--color-text)' }}>
            <Target size={18} /> {t('planejador.title')}
          </h1>
          <p className="text-sm mt-2 max-w-2xl" style={{ color: 'var(--color-text-secondary)' }}>
            {t('planejador.subtitle')}
          </p>
          <p className="text-xs mt-1 max-w-2xl" style={{ color: 'var(--color-text-tertiary)' }}>
            {t('planejador.hint')}
          </p>
        </header>

        <div className="rounded-xl p-4 mb-5 space-y-3" style={card}>
          <label className="block text-xs" style={{ color: 'var(--color-text-secondary)' }}>
            {t('planejador.form.goal')}
            <input
              value={goal}
              maxLength={300}
              onChange={(e) => setGoal(e.target.value)}
              placeholder={t('planejador.form.goalPlaceholder')}
              className="mt-1 w-full px-3 py-1.5 rounded-lg text-sm"
              style={input}
              disabled={proposing}
              data-testid="planner-goal"
            />
          </label>
          <div className="flex flex-col sm:flex-row sm:items-end gap-2">
            <label className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              {t('planejador.form.deadline')}
              <input
                type="date"
                value={deadline}
                min={tomorrow()}
                onChange={(e) => setDeadline(e.target.value)}
                className="mt-1 block px-3 py-1.5 rounded-lg text-sm"
                style={input}
                disabled={proposing}
                data-testid="planner-deadline"
              />
            </label>
            <div className="flex-1 flex items-center gap-1.5">
              <input
                value={deadlineText}
                onChange={(e) => setDeadlineText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') void resolveDeadline();
                }}
                placeholder={t('planejador.form.deadlineTextPlaceholder')}
                aria-label={t('planejador.form.deadlineText')}
                className="flex-1 min-w-0 px-3 py-1.5 rounded-lg text-sm"
                style={input}
                disabled={proposing}
                data-testid="planner-deadline-text"
              />
              <button
                type="button"
                onClick={() => void resolveDeadline()}
                disabled={!deadlineText.trim() || proposing}
                className={buttonClass}
                style={secondaryButton}
                data-testid="planner-deadline-resolve"
              >
                {t('planejador.form.useDeadline')}
              </button>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => void propose()}
              disabled={!ready || proposing}
              className={buttonClass}
              style={primaryButton}
              data-testid="planner-propose"
            >
              {proposing ? <Loader2 size={12} className="animate-spin" /> : <Target size={12} />}
              {t(steps ? 'planejador.form.proposeAgain' : 'planejador.form.propose')}
            </button>
            {proposing && (
              <button type="button" onClick={cancel} className={buttonClass} style={secondaryButton} data-testid="planner-cancel">
                <X size={12} /> {t('planejador.form.cancel')}
              </button>
            )}
          </div>
          {proposing && (
            <p className="text-xs" role="status" style={{ color: 'var(--color-text-secondary)' }} data-testid="planner-waiting">
              {t('planejador.form.waiting')}
            </p>
          )}
          {error && (
            <div className="text-sm" role="alert" style={{ color: 'var(--color-error)' }}>
              {error}
            </div>
          )}
        </div>

        {steps && (
          <div className="rounded-xl p-4 mb-5 space-y-3" style={card} data-testid="planner-steps">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                {t('planejador.steps.title')}
              </h2>
              <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                {t('planejador.steps.total', { n: steps.length, hours: Math.round((totalMinutes / 60) * 10) / 10 })}
              </span>
            </div>
            <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
              {t('planejador.steps.hint')}
            </p>
            <ol className="space-y-1.5">
              {steps.map((s, i) => (
                <li
                  key={i}
                  className="flex flex-wrap items-center gap-1.5 p-2 rounded-lg"
                  style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border-subtle)' }}
                  data-testid={`planner-step-${i}`}
                >
                  <span className="text-xs tabular-nums w-6 shrink-0" style={{ color: 'var(--color-text-tertiary)' }}>
                    #{i + 1}
                  </span>
                  <input
                    value={s.texto}
                    maxLength={300}
                    onChange={(e) => setStep(i, { texto: e.target.value })}
                    aria-label={t('planejador.steps.text')}
                    className={`${field} flex-1`}
                    style={input}
                    data-testid={`planner-step-text-${i}`}
                  />
                  <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                    <input
                      type="number"
                      min={15}
                      max={6000}
                      step={15}
                      value={s.minutos || ''}
                      onChange={(e) => setStep(i, { minutos: Number(e.target.value) || 0 })}
                      className={`${field} w-16`}
                      style={input}
                      data-testid={`planner-step-minutes-${i}`}
                    />
                    {t('planejador.steps.minutes')}
                  </label>
                  {s.depende_de.length > 0 && (
                    <span className="text-[11px]" style={{ color: 'var(--color-text-tertiary)' }}>
                      {t('planejador.steps.after', { steps: s.depende_de.map((d) => `#${d + 1}`).join(', ') })}
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => setSteps((list) => (list ? removeStep(list, i) : list))}
                    className="p-1 rounded cursor-pointer ms-auto"
                    style={{ color: 'var(--color-text-tertiary)' }}
                    aria-label={t('planejador.steps.remove')}
                    data-testid={`planner-step-remove-${i}`}
                  >
                    <Trash2 size={12} />
                  </button>
                </li>
              ))}
            </ol>
            <button
              type="button"
              onClick={() =>
                setSteps((list) => (list && list.length < 12 ? [...list, { texto: '', minutos: 60, depende_de: [] }] : list))
              }
              disabled={steps.length >= 12}
              className={buttonClass}
              style={secondaryButton}
              data-testid="planner-add-step"
            >
              <Plus size={12} /> {t('planejador.steps.add')}
            </button>
            <label className="block text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              {t('planejador.steps.name')}
              <input
                value={name}
                maxLength={80}
                onChange={(e) => setName(e.target.value)}
                placeholder={goal.trim() || t('planejador.steps.namePlaceholder')}
                className="mt-1 w-full px-3 py-1.5 rounded-lg text-sm"
                style={input}
                data-testid="planner-name"
              />
            </label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => void create()}
                disabled={creating || steps.length === 0 || !deadline}
                className={buttonClass}
                style={primaryButton}
                data-testid="planner-create"
              >
                {creating ? t('planejador.steps.creating') : t('planejador.steps.create')}
              </button>
              <button type="button" onClick={() => setSteps(null)} className={buttonClass} style={secondaryButton}>
                {t('planejador.steps.discard')}
              </button>
            </div>
          </div>
        )}

        {created && (
          <div className="rounded-xl p-4 mb-5 text-sm" role="status" style={card} data-testid="planner-created">
            <div className="font-semibold" style={{ color: 'var(--color-text)' }}>
              {t('planejador.created.title', { name: created.progresso.nome || created.projeto.nome })}
            </div>
            <p className="text-xs mt-1" style={{ color: 'var(--color-text-secondary)' }}>
              {t('planejador.created.summary', {
                n: created.progresso.total,
                date: formatDay(created.progresso.prazo || created.projeto.prazo, i18n.language),
              })}
            </p>
            {created.progresso.proxima && (
              <p className="text-xs mt-1" style={{ color: 'var(--color-text-secondary)' }}>
                {t('planejador.plans.next', {
                  step: created.progresso.proxima.texto,
                  date: formatDay(created.progresso.proxima.prazo, i18n.language),
                })}
              </p>
            )}
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                onClick={() => navigate('/projetos', { state: { projeto: created.projeto.id } })}
                className={buttonClass}
                style={secondaryButton}
              >
                <ExternalLink size={12} /> {t('planejador.plans.openProject')}
              </button>
              <button type="button" onClick={() => setCreated(null)} className={buttonClass} style={secondaryButton}>
                {t('planejador.dismiss')}
              </button>
            </div>
          </div>
        )}

        <section>
          <h2 className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--color-text-tertiary)' }}>
            {t('planejador.plans.title')}
          </h2>
          {plansError && (
            <div className="mb-3 text-sm rounded-lg px-3 py-2" role="alert" style={{ ...card, color: 'var(--color-error)' }}>
              {plansError}
            </div>
          )}
          {loadingPlans ? (
            <p className="text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
              {t('planejador.loading')}
            </p>
          ) : plans.length === 0 && !plansError ? (
            <p className="text-sm" style={{ color: 'var(--color-text-tertiary)' }} data-testid="plans-empty">
              {t('planejador.plans.empty')}
            </p>
          ) : (
            <ul className="space-y-3" data-testid="plans-list">
              {plans.map((p) => (
                <PlanCard
                  key={p.projeto}
                  plan={p}
                  onChange={(updated) => setPlans((list) => list.map((x) => (x.projeto === updated.projeto ? updated : x)))}
                />
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

export default PlannerPage;
