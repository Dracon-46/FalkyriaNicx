import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import { ArrowDown, ArrowUp, Pencil, Play, Plus, Repeat, Sparkles, Trash2, Wand2, X } from 'lucide-react';
import {
  MAX_NAME,
  MAX_PHRASES,
  MAX_STEPS,
  STEP_KINDS,
  TIMER_TEXT,
  WEEKDAYS,
  apagarRotina,
  atualizarRotina,
  criarRotina,
  emptyStep,
  executarRotina,
  interpretarRotina,
  listarRotinas,
  opcoesRotinas,
  type Interpretation,
  type Routine,
  type RoutineInput,
  type RoutineOptions,
  type RoutineStep,
  type RunResult,
  type Weekday,
} from '../lib/rotinas';

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
const iconButton = 'p-1 rounded cursor-pointer disabled:opacity-40 disabled:cursor-default';
const field = 'px-2 py-1 rounded text-xs min-w-0';

const VOLUME_OPS = ['up', 'down', 'set', 'mute'] as const;
const MEDIA_OPS = ['toggle', 'next', 'prev'] as const;
const SITES: Record<string, string> = { google: 'Google', youtube: 'YouTube' };
const WORKDAYS: Weekday[] = ['seg', 'ter', 'qua', 'qui', 'sex'];
const EMPTY_OPTIONS: RoutineOptions = { tipos: [...STEP_KINDS], apps: [], fechar: [], pastas: [] };

interface Draft {
  /** Sem id: rotina nova (ou a partir de um modelo). */
  id?: string;
  nome: string;
  frases: string[];
  agendada: boolean;
  dias: Weekday[];
  hora: string;
  passos: RoutineStep[];
  ativa: boolean;
}

function draftOf(rotina?: Routine, keepId = true): Draft {
  return {
    id: keepId ? rotina?.id : undefined,
    nome: rotina?.nome ?? '',
    frases: [...(rotina?.frases ?? [])],
    agendada: Boolean(rotina?.agenda),
    dias: [...(rotina?.agenda?.dias ?? [])],
    hora: rotina?.agenda?.hora ?? '08:00',
    passos: (rotina?.passos ?? []).map((p) => ({ ...p })),
    ativa: rotina?.ativa ?? true,
  };
}

function toInput(rotina: Routine, idioma: string): RoutineInput {
  return {
    nome: rotina.nome,
    passos: rotina.passos,
    frases: rotina.frases,
    agenda: rotina.agenda,
    ativa: rotina.ativa,
    idioma: rotina.idioma || idioma,
  };
}

function label(list: { chave: string; rotulo: string }[], key: string): string {
  return list.find((x) => x.chave === key)?.rotulo ?? key;
}

/** Uma linha legível do passo: "Abrir Chrome", "Volume em 30%"... */
function describeStep(step: RoutineStep, options: RoutineOptions, t: TFunction): string {
  const target = step.target;
  switch (step.kind) {
    case 'volume':
      return t(`rotinas.summary.volume_${step.op || 'set'}`, { value: step.value ?? '', defaultValue: t('rotinas.kinds.volume') });
    case 'media':
      return t(`rotinas.summary.media_${step.op || 'toggle'}`, { defaultValue: t('rotinas.kinds.media') });
    case 'open':
      return t('rotinas.summary.open', { target: label(options.apps, target) });
    case 'close':
      return t('rotinas.summary.close', { target: label(options.fechar, target) });
    case 'folder':
      return t('rotinas.summary.folder', { target: t(`rotinas.folders.${target}`, { defaultValue: target }) });
    case 'search':
      return t('rotinas.summary.search', { target, site: SITES[step.site] ?? SITES.google });
    case 'remind':
      return !target || target === TIMER_TEXT
        ? t('rotinas.summary.timer', { minutos: step.minutos ?? 0 })
        : t('rotinas.summary.remind', { target, minutos: step.minutos ?? 0 });
    case 'open_url':
    case 'youtube':
    case 'note_add':
      return t(`rotinas.summary.${step.kind}`, { target });
    default:
      return t(`rotinas.summary.${step.kind}`, { defaultValue: step.kind });
  }
}

/** "Seg, Qua · 09:00", "Dias úteis · 08:00" ou "Sem horário". */
function scheduleSummary(rotina: Pick<Routine, 'agenda'>, t: TFunction): string {
  const agenda = rotina.agenda;
  if (!agenda || agenda.dias.length === 0) return t('rotinas.noSchedule');
  const dias = WEEKDAYS.filter((d) => agenda.dias.includes(d));
  let days: string;
  if (dias.length === 7) days = t('rotinas.everyDay');
  else if (dias.length === 5 && WORKDAYS.every((d) => dias.includes(d))) days = t('rotinas.workdays');
  else days = dias.map((d) => t(`rotinas.days.${d}`)).join(', ');
  return `${days} · ${agenda.hora}`;
}

/** Limpa os campos que o tipo não usa e confere o que falta. Devolve null se faltar algo. */
function cleanStep(step: RoutineStep): RoutineStep | null {
  const s = emptyStep(step.kind);
  const target = step.target.trim();
  switch (step.kind) {
    case 'volume': {
      s.op = (VOLUME_OPS as readonly string[]).includes(step.op) ? step.op : 'set';
      if (s.op === 'set') s.value = Math.max(0, Math.min(100, Math.round(step.value ?? 30)));
      else if (s.op !== 'mute') s.value = Math.max(1, Math.min(50, Math.round(step.value ?? 2)));
      return s;
    }
    case 'media':
      s.op = (MEDIA_OPS as readonly string[]).includes(step.op) ? step.op : 'toggle';
      return s;
    case 'open_url':
      if (!target) return null;
      s.target = /^https?:\/\//i.test(target) ? target : `https://${target}`;
      return s;
    case 'search':
      if (!target) return null;
      s.target = target;
      s.site = step.site in SITES ? step.site : 'google';
      return s;
    case 'open':
    case 'close':
    case 'folder':
    case 'youtube':
    case 'note_add':
      if (!target) return null;
      s.target = target;
      return s;
    case 'remind':
      if (!step.minutos || step.minutos < 1) return null;
      s.minutos = Math.round(step.minutos);
      s.target = target || TIMER_TEXT;
      return s;
    default:
      return s;
  }
}

function numberOrNull(value: string): number | null {
  if (value.trim() === '') return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

/** Select de chave/rótulo; vira texto livre se o servidor não mandou a lista. */
function KeySelect({
  value,
  items,
  onChange,
  testId,
  ariaLabel,
}: {
  value: string;
  items: { chave: string; rotulo: string }[];
  onChange: (value: string) => void;
  testId: string;
  ariaLabel: string;
}) {
  const { t } = useTranslation();
  if (items.length === 0) {
    return (
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`${field} flex-1`}
        style={input}
        aria-label={ariaLabel}
        data-testid={testId}
      />
    );
  }
  // O catálogo tem apelidos (chrome, google chrome): um item por rótulo.
  const seen = new Set<string>();
  const unique = items.filter((x) => (seen.has(x.rotulo) ? false : (seen.add(x.rotulo), true)));
  if (value && !unique.some((x) => x.chave === value)) unique.push({ chave: value, rotulo: label(items, value) });
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={`${field} flex-1`}
      style={input}
      aria-label={ariaLabel}
      data-testid={testId}
    >
      <option value="">{t('rotinas.editor.choose')}</option>
      {unique.map((x) => (
        <option key={x.chave} value={x.chave}>
          {x.rotulo}
        </option>
      ))}
    </select>
  );
}

function StepFields({
  step,
  index,
  options,
  onChange,
}: {
  step: RoutineStep;
  index: number;
  options: RoutineOptions;
  onChange: (step: RoutineStep) => void;
}) {
  const { t } = useTranslation();
  const set = (patch: Partial<RoutineStep>) => onChange({ ...step, ...patch });
  const id = (name: string) => `routine-step-${name}-${index}`;
  const text = (placeholder: string) => (
    <input
      value={step.target}
      onChange={(e) => set({ target: e.target.value })}
      placeholder={placeholder}
      aria-label={placeholder}
      className={`${field} flex-1`}
      style={input}
      data-testid={id('target')}
    />
  );

  switch (step.kind) {
    case 'volume':
      return (
        <>
          <select
            value={step.op || 'set'}
            onChange={(e) => set({ op: e.target.value, value: null })}
            className={field}
            style={input}
            aria-label={t('rotinas.editor.operation')}
            data-testid={id('op')}
          >
            {VOLUME_OPS.map((op) => (
              <option key={op} value={op}>
                {t(`rotinas.ops.volume.${op}`)}
              </option>
            ))}
          </select>
          {(step.op || 'set') !== 'mute' && (
            <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              {t((step.op || 'set') === 'set' ? 'rotinas.editor.level' : 'rotinas.editor.steps')}
              <input
                type="number"
                min={(step.op || 'set') === 'set' ? 0 : 1}
                max={(step.op || 'set') === 'set' ? 100 : 50}
                value={step.value ?? ''}
                onChange={(e) => set({ value: numberOrNull(e.target.value) })}
                className={`${field} w-16`}
                style={input}
                data-testid={id('value')}
              />
            </label>
          )}
        </>
      );
    case 'media':
      return (
        <select
          value={step.op || 'toggle'}
          onChange={(e) => set({ op: e.target.value })}
          className={field}
          style={input}
          aria-label={t('rotinas.editor.operation')}
          data-testid={id('op')}
        >
          {MEDIA_OPS.map((op) => (
            <option key={op} value={op}>
              {t(`rotinas.ops.media.${op}`)}
            </option>
          ))}
        </select>
      );
    case 'open':
      return (
        <KeySelect
          value={step.target}
          items={options.apps}
          onChange={(target) => set({ target })}
          testId={id('target')}
          ariaLabel={t('rotinas.editor.app')}
        />
      );
    case 'close':
      return (
        <KeySelect
          value={step.target}
          items={options.fechar}
          onChange={(target) => set({ target })}
          testId={id('target')}
          ariaLabel={t('rotinas.editor.app')}
        />
      );
    case 'folder':
      return (
        <KeySelect
          value={step.target}
          items={options.pastas.map((p) => ({ chave: p, rotulo: t(`rotinas.folders.${p}`, { defaultValue: p }) }))}
          onChange={(target) => set({ target })}
          testId={id('target')}
          ariaLabel={t('rotinas.editor.folder')}
        />
      );
    case 'open_url':
      return text(t('rotinas.editor.url'));
    case 'youtube':
      return text(t('rotinas.editor.youtube'));
    case 'note_add':
      return text(t('rotinas.editor.note'));
    case 'search':
      return (
        <>
          {text(t('rotinas.editor.searchTerm'))}
          <select
            value={step.site || 'google'}
            onChange={(e) => set({ site: e.target.value })}
            className={field}
            style={input}
            aria-label={t('rotinas.editor.site')}
            data-testid={id('site')}
          >
            {Object.entries(SITES).map(([key, name]) => (
              <option key={key} value={key}>
                {name}
              </option>
            ))}
          </select>
        </>
      );
    case 'remind':
      return (
        <>
          <input
            value={step.target === TIMER_TEXT ? '' : step.target}
            onChange={(e) => set({ target: e.target.value })}
            placeholder={t('rotinas.editor.remindText')}
            aria-label={t('rotinas.editor.remindText')}
            className={`${field} flex-1`}
            style={input}
            data-testid={id('target')}
          />
          <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
            {t('rotinas.editor.inMinutes')}
            <input
              type="number"
              min={1}
              max={1440}
              value={step.minutos ?? ''}
              onChange={(e) => set({ minutos: numberOrNull(e.target.value) })}
              className={`${field} w-16`}
              style={input}
              data-testid={id('minutos')}
            />
          </label>
        </>
      );
    default:
      return (
        <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
          {t('rotinas.editor.noFields')}
        </span>
      );
  }
}

function Editor({
  initial,
  options,
  onSaved,
  onCancel,
}: {
  initial: Draft;
  options: RoutineOptions;
  onSaved: (rotina: Routine) => void;
  onCancel: () => void;
}) {
  const { t, i18n } = useTranslation();
  const [draft, setDraft] = useState<Draft>(initial);
  const [phrase, setPhrase] = useState('');
  const [description, setDescription] = useState('');
  const [interpreting, setInterpreting] = useState(false);
  const [warnings, setWarnings] = useState<Pick<Interpretation, 'nao_entendi' | 'proibidos'> | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const update = (patch: Partial<Draft>) => setDraft((d) => ({ ...d, ...patch }));
  const setStep = (i: number, step: RoutineStep) =>
    setDraft((d) => ({ ...d, passos: d.passos.map((p, j) => (j === i ? step : p)) }));
  const move = (i: number, delta: number) =>
    setDraft((d) => {
      const passos = [...d.passos];
      const j = i + delta;
      if (j < 0 || j >= passos.length) return d;
      [passos[i], passos[j]] = [passos[j], passos[i]];
      return { ...d, passos };
    });
  const remove = (i: number) => setDraft((d) => ({ ...d, passos: d.passos.filter((_, j) => j !== i) }));
  const addStep = () => setDraft((d) => (d.passos.length >= MAX_STEPS ? d : { ...d, passos: [...d.passos, emptyStep('open')] }));

  const addPhrase = () => {
    const value = phrase.trim().slice(0, MAX_NAME);
    if (!value || draft.frases.length >= MAX_PHRASES) return;
    if (!draft.frases.some((f) => f.toLowerCase() === value.toLowerCase())) update({ frases: [...draft.frases, value] });
    setPhrase('');
  };

  const toggleDay = (dia: Weekday) =>
    update({ dias: draft.dias.includes(dia) ? draft.dias.filter((d) => d !== dia) : [...draft.dias, dia] });

  const kinds = (options.tipos.length ? options.tipos : [...STEP_KINDS]).filter((k) =>
    (STEP_KINDS as readonly string[]).includes(k),
  );

  const interpret = async () => {
    const texto = description.trim();
    if (!texto) return;
    setInterpreting(true);
    setError('');
    try {
      const result = await interpretarRotina(texto, i18n.language);
      setDraft((d) => ({
        ...d,
        passos: [...d.passos, ...result.passos].slice(0, MAX_STEPS),
        ...(result.agenda
          ? { agendada: true, dias: [...result.agenda.dias], hora: result.agenda.hora }
          : {}),
      }));
      setWarnings(
        result.nao_entendi.length || result.proibidos.length
          ? { nao_entendi: result.nao_entendi, proibidos: result.proibidos }
          : null,
      );
      if (result.passos.length || result.agenda) setDescription('');
    } catch (e) {
      setError(e instanceof Error ? e.message : t('rotinas.interpretFailed'));
    } finally {
      setInterpreting(false);
    }
  };

  const save = async () => {
    const nome = draft.nome.trim();
    if (!nome) return setError(t('rotinas.editor.needName'));
    if (draft.passos.length === 0) return setError(t('rotinas.editor.needStep'));
    const passos: RoutineStep[] = [];
    for (const [i, step] of draft.passos.entries()) {
      const clean = cleanStep(step);
      if (!clean) return setError(t('rotinas.editor.incompleteStep', { n: i + 1 }));
      passos.push(clean);
    }
    if (draft.agendada && (draft.dias.length === 0 || !/^\d{2}:\d{2}$/.test(draft.hora))) {
      return setError(t('rotinas.editor.needSchedule'));
    }
    const body: RoutineInput = {
      nome,
      passos,
      frases: draft.frases,
      agenda: draft.agendada ? { dias: WEEKDAYS.filter((d) => draft.dias.includes(d)), hora: draft.hora } : null,
      ativa: draft.ativa,
      idioma: i18n.language,
    };
    setSaving(true);
    setError('');
    try {
      onSaved(draft.id ? await atualizarRotina(draft.id, body) : await criarRotina(body));
    } catch (e) {
      setError(e instanceof Error ? e.message : t('rotinas.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-xl p-4 mb-5 space-y-4" style={card} data-testid="routine-editor">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
          {t(draft.id ? 'rotinas.editor.editTitle' : 'rotinas.editor.newTitle')}
        </h2>
        <button
          type="button"
          onClick={onCancel}
          className={iconButton}
          style={{ color: 'var(--color-text-tertiary)' }}
          aria-label={t('rotinas.editor.cancel')}
        >
          <X size={14} />
        </button>
      </div>

      <label className="block text-xs" style={{ color: 'var(--color-text-secondary)' }}>
        {t('rotinas.editor.name')}
        <input
          value={draft.nome}
          maxLength={MAX_NAME}
          onChange={(e) => update({ nome: e.target.value })}
          placeholder={t('rotinas.editor.namePlaceholder')}
          className="mt-1 w-full px-3 py-1.5 rounded-lg text-sm"
          style={input}
          data-testid="routine-name"
        />
      </label>

      <div>
        <div className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          {t('rotinas.editor.phrases')}
        </div>
        <div className="text-[11px] mb-1" style={{ color: 'var(--color-text-tertiary)' }}>
          {t('rotinas.editor.phrasesHint', { max: MAX_PHRASES })}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {draft.frases.map((f) => (
            <span
              key={f}
              className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
              style={secondaryButton}
              data-testid="routine-phrase"
            >
              {f}
              <button
                type="button"
                onClick={() => update({ frases: draft.frases.filter((x) => x !== f) })}
                className="cursor-pointer"
                aria-label={t('rotinas.editor.removePhrase', { phrase: f })}
              >
                <X size={10} />
              </button>
            </span>
          ))}
          {draft.frases.length < MAX_PHRASES && (
            <span className="flex items-center gap-1">
              <input
                value={phrase}
                onChange={(e) => setPhrase(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    addPhrase();
                  }
                }}
                placeholder={t('rotinas.editor.phrasePlaceholder')}
                aria-label={t('rotinas.editor.phrases')}
                className={field}
                style={input}
                data-testid="routine-phrase-input"
              />
              <button
                type="button"
                onClick={addPhrase}
                disabled={!phrase.trim()}
                className={iconButton}
                style={{ color: 'var(--color-text-secondary)' }}
                aria-label={t('rotinas.editor.addPhrase')}
                data-testid="routine-phrase-add"
              >
                <Plus size={13} />
              </button>
            </span>
          )}
        </div>
      </div>

      <div>
        <label className="flex items-center gap-2 text-xs cursor-pointer" style={{ color: 'var(--color-text-secondary)' }}>
          <input
            type="checkbox"
            checked={draft.agendada}
            onChange={(e) => update({ agendada: e.target.checked })}
            data-testid="routine-schedule-toggle"
          />
          {t('rotinas.editor.schedule')}
        </label>
        {draft.agendada && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {WEEKDAYS.map((dia) => {
              const on = draft.dias.includes(dia);
              return (
                <button
                  key={dia}
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggleDay(dia)}
                  className="px-2.5 py-1 rounded-full text-xs font-medium cursor-pointer"
                  style={{
                    background: on ? 'var(--color-accent)' : 'var(--color-bg)',
                    color: on ? '#fff' : 'var(--color-text-secondary)',
                    border: '1px solid var(--color-border)',
                  }}
                  data-testid={`routine-day-${dia}`}
                >
                  {t(`rotinas.days.${dia}`)}
                </button>
              );
            })}
            <input
              type="time"
              value={draft.hora}
              onChange={(e) => update({ hora: e.target.value })}
              aria-label={t('rotinas.editor.time')}
              className={field}
              style={input}
              data-testid="routine-time"
            />
          </div>
        )}
        {draft.agendada && (
          <p className="text-[11px] mt-1" style={{ color: 'var(--color-text-tertiary)' }}>
            {t('rotinas.editor.scheduleHint')}
          </p>
        )}
      </div>

      <div>
        <div className="text-xs mb-1.5" style={{ color: 'var(--color-text-secondary)' }}>
          {t('rotinas.editor.stepsTitle', { n: draft.passos.length, max: MAX_STEPS })}
        </div>
        {draft.passos.length === 0 && (
          <p className="text-xs mb-2" style={{ color: 'var(--color-text-tertiary)' }}>
            {t('rotinas.editor.noSteps')}
          </p>
        )}
        <ol className="space-y-1.5">
          {draft.passos.map((step, i) => (
            <li
              key={i}
              className="flex flex-wrap items-center gap-1.5 p-2 rounded-lg"
              style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border-subtle)' }}
              data-testid={`routine-step-${i}`}
            >
              <span className="text-xs tabular-nums w-5 shrink-0" style={{ color: 'var(--color-text-tertiary)' }}>
                {i + 1}.
              </span>
              <select
                value={step.kind}
                onChange={(e) => setStep(i, emptyStep(e.target.value))}
                className={field}
                style={input}
                aria-label={t('rotinas.editor.kind')}
                data-testid={`routine-step-kind-${i}`}
              >
                {kinds.map((k) => (
                  <option key={k} value={k}>
                    {t(`rotinas.kinds.${k}`, { defaultValue: k })}
                  </option>
                ))}
              </select>
              <StepFields step={step} index={i} options={options} onChange={(s) => setStep(i, s)} />
              <span className="flex items-center gap-0.5 ms-auto" style={{ color: 'var(--color-text-tertiary)' }}>
                <button
                  type="button"
                  onClick={() => move(i, -1)}
                  disabled={i === 0}
                  className={iconButton}
                  aria-label={t('rotinas.editor.moveUp')}
                  data-testid={`routine-step-up-${i}`}
                >
                  <ArrowUp size={12} />
                </button>
                <button
                  type="button"
                  onClick={() => move(i, 1)}
                  disabled={i === draft.passos.length - 1}
                  className={iconButton}
                  aria-label={t('rotinas.editor.moveDown')}
                  data-testid={`routine-step-down-${i}`}
                >
                  <ArrowDown size={12} />
                </button>
                <button
                  type="button"
                  onClick={() => remove(i)}
                  className={iconButton}
                  aria-label={t('rotinas.editor.removeStep')}
                  data-testid={`routine-step-remove-${i}`}
                >
                  <Trash2 size={12} />
                </button>
              </span>
            </li>
          ))}
        </ol>
        <button
          type="button"
          onClick={addStep}
          disabled={draft.passos.length >= MAX_STEPS}
          className={`${buttonClass} mt-2`}
          style={secondaryButton}
          data-testid="routine-add-step"
        >
          <Plus size={12} /> {t('rotinas.editor.addStep')}
        </button>
      </div>

      <div className="rounded-lg p-3" style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border-subtle)' }}>
        <div className="text-xs font-medium flex items-center gap-1.5" style={{ color: 'var(--color-text-secondary)' }}>
          <Wand2 size={12} /> {t('rotinas.editor.describe')}
        </div>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
          maxLength={1000}
          placeholder={t('rotinas.editor.describePlaceholder')}
          aria-label={t('rotinas.editor.describe')}
          className="mt-1.5 w-full px-3 py-1.5 rounded-lg text-sm resize-y"
          style={input}
          data-testid="routine-describe"
        />
        <button
          type="button"
          onClick={() => void interpret()}
          disabled={!description.trim() || interpreting}
          className={`${buttonClass} mt-1.5`}
          style={secondaryButton}
          data-testid="routine-interpret"
        >
          <Sparkles size={12} /> {interpreting ? t('rotinas.editor.interpreting') : t('rotinas.editor.interpret')}
        </button>
        {warnings && (
          <div className="mt-2 text-xs space-y-1" style={{ color: 'var(--color-warning)' }} data-testid="routine-warnings">
            {warnings.nao_entendi.length > 0 && (
              <div>{t('rotinas.editor.notUnderstood', { items: warnings.nao_entendi.join('; ') })}</div>
            )}
            {warnings.proibidos.length > 0 && (
              <div>{t('rotinas.editor.forbidden', { items: warnings.proibidos.join('; ') })}</div>
            )}
          </div>
        )}
      </div>

      {error && (
        <div className="text-sm" role="alert" style={{ color: 'var(--color-error)' }}>
          {error}
        </div>
      )}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => void save()}
          disabled={saving}
          className={buttonClass}
          style={primaryButton}
          data-testid="routine-save"
        >
          {saving ? t('rotinas.editor.saving') : t('rotinas.editor.save')}
        </button>
        <button type="button" onClick={onCancel} className={buttonClass} style={secondaryButton} data-testid="routine-cancel">
          {t('rotinas.editor.cancel')}
        </button>
      </div>
    </div>
  );
}

function RoutineCard({
  rotina,
  options,
  template,
  busy,
  onRun,
  onEdit,
  onDelete,
  onToggle,
}: {
  rotina: Routine;
  options: RoutineOptions;
  template?: boolean;
  busy: boolean;
  onRun: () => void;
  onEdit: () => void;
  onDelete?: () => void;
  onToggle?: (ativa: boolean) => void;
}) {
  const { t, i18n } = useTranslation();
  const prefix = template ? 'template' : 'routine';
  const last = rotina.ultima_execucao ? new Date(rotina.ultima_execucao) : null;
  const lastText =
    last && !Number.isNaN(last.getTime())
      ? last.toLocaleString(i18n.language, { dateStyle: 'short', timeStyle: 'short' })
      : '';

  return (
    <li className="rounded-xl p-4" style={card} data-testid={`${prefix}-card-${rotina.id}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div
            className="text-sm font-semibold break-words"
            style={{ color: template || rotina.ativa ? 'var(--color-text)' : 'var(--color-text-tertiary)' }}
          >
            {rotina.nome}
          </div>
          <div className="text-xs mt-0.5" style={{ color: 'var(--color-text-tertiary)' }}>
            {scheduleSummary(rotina, t)}
            {!template && ` · ${lastText ? t('rotinas.lastRun', { when: lastText }) : t('rotinas.neverRun')}`}
          </div>
        </div>
        {onToggle && (
          <label className="flex items-center gap-1.5 text-xs cursor-pointer" style={{ color: 'var(--color-text-secondary)' }}>
            <input
              type="checkbox"
              checked={rotina.ativa}
              disabled={busy}
              onChange={(e) => onToggle(e.target.checked)}
              data-testid={`routine-toggle-${rotina.id}`}
            />
            {t('rotinas.active')}
          </label>
        )}
      </div>
      <ol className="mt-2 text-xs space-y-0.5 list-decimal ps-5" style={{ color: 'var(--color-text-secondary)' }}>
        {rotina.passos.map((p, i) => (
          <li key={i} className="break-words">
            {describeStep(p, options, t)}
          </li>
        ))}
      </ol>
      {rotina.frases.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {rotina.frases.map((f) => (
            <span key={f} className="text-[10px] px-1.5 py-0.5 rounded" style={secondaryButton}>
              “{f}”
            </span>
          ))}
        </div>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onRun}
          disabled={busy}
          className={buttonClass}
          style={primaryButton}
          data-testid={`${prefix}-run-${rotina.id}`}
        >
          <Play size={12} /> {t('rotinas.runNow')}
        </button>
        <button
          type="button"
          onClick={onEdit}
          className={buttonClass}
          style={secondaryButton}
          data-testid={template ? `template-use-${rotina.id}` : `routine-edit-${rotina.id}`}
        >
          {template ? <Plus size={12} /> : <Pencil size={12} />} {t(template ? 'rotinas.useTemplate' : 'rotinas.edit')}
        </button>
        {onDelete && (
          <button
            type="button"
            onClick={onDelete}
            disabled={busy}
            className={buttonClass}
            style={secondaryButton}
            data-testid={`routine-delete-${rotina.id}`}
          >
            <Trash2 size={12} /> {t('rotinas.delete')}
          </button>
        )}
      </div>
    </li>
  );
}

export function RoutinesPage() {
  const { t, i18n } = useTranslation();
  const [rotinas, setRotinas] = useState<Routine[]>([]);
  const [modelos, setModelos] = useState<Routine[]>([]);
  const [options, setOptions] = useState<RoutineOptions>(EMPTY_OPTIONS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState<RunResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [editing, setEditing] = useState<{ key: number; draft: Draft } | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await listarRotinas(i18n.language);
      setRotinas(data.rotinas);
      setModelos(data.modelos);
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : t('rotinas.loadFailed'));
    } finally {
      setLoading(false);
    }
  }, [i18n.language, t]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    let cancelled = false;
    opcoesRotinas()
      .then((o) => {
        if (!cancelled) setOptions(o);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const edit = (draft: Draft) => {
    setEditing({ key: Date.now(), draft });
    setNotice(null);
  };

  const run = async (rotina: Routine) => {
    setBusy(rotina.id);
    try {
      setNotice(await executarRotina(rotina.id, i18n.language));
      void load();
    } catch (e) {
      setNotice({ ok: false, mensagem: e instanceof Error ? e.message : t('rotinas.runFailed') });
    } finally {
      setBusy(null);
    }
  };

  const toggle = async (rotina: Routine, ativa: boolean) => {
    setBusy(rotina.id);
    try {
      const saved = await atualizarRotina(rotina.id, { ...toInput(rotina, i18n.language), ativa });
      setRotinas((list) => list.map((r) => (r.id === saved.id ? saved : r)));
    } catch (e) {
      setNotice({ ok: false, mensagem: e instanceof Error ? e.message : t('rotinas.saveFailed') });
    } finally {
      setBusy(null);
    }
  };

  const remove = async (rotina: Routine) => {
    if (!window.confirm(t('rotinas.confirmDelete', { name: rotina.nome }))) return;
    setBusy(rotina.id);
    try {
      await apagarRotina(rotina.id);
      setRotinas((list) => list.filter((r) => r.id !== rotina.id));
      if (editing?.draft.id === rotina.id) setEditing(null);
      setNotice({ ok: true, mensagem: t('rotinas.deleted', { name: rotina.nome }) });
    } catch (e) {
      setNotice({ ok: false, mensagem: e instanceof Error ? e.message : t('rotinas.deleteFailed') });
    } finally {
      setBusy(null);
    }
  };

  const saved = (rotina: Routine) => {
    setEditing(null);
    setNotice({ ok: true, mensagem: t('rotinas.saved', { name: rotina.nome }) });
    void load();
  };

  return (
    <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-10">
      <div className="max-w-3xl mx-auto">
        <header className="mb-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h1 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--color-text)' }}>
              <Repeat size={18} /> {t('rotinas.title')}
            </h1>
            <button
              type="button"
              onClick={() => edit(draftOf())}
              className={buttonClass}
              style={secondaryButton}
              data-testid="routine-new"
            >
              <Plus size={12} /> {t('rotinas.new')}
            </button>
          </div>
          <p className="text-sm mt-2 max-w-2xl" style={{ color: 'var(--color-text-secondary)' }}>
            {t('rotinas.subtitle')}
          </p>
          <p className="text-xs mt-1 max-w-2xl" style={{ color: 'var(--color-text-tertiary)' }}>
            {t('rotinas.hint')}
          </p>
        </header>

        {notice && (
          <div
            className="mb-4 text-sm rounded-lg px-3 py-2 flex items-start justify-between gap-3"
            role="status"
            style={{ ...card, color: notice.ok ? 'var(--color-text)' : 'var(--color-error)' }}
            data-testid="routine-notice"
          >
            <span className="min-w-0 break-words whitespace-pre-line">{notice.mensagem}</span>
            <button
              type="button"
              onClick={() => setNotice(null)}
              className="text-xs shrink-0 cursor-pointer"
              style={{ color: 'var(--color-text-tertiary)' }}
            >
              {t('rotinas.dismiss')}
            </button>
          </div>
        )}

        {error && (
          <div className="mb-4 text-sm rounded-lg px-3 py-2" role="alert" style={{ ...card, color: 'var(--color-error)' }}>
            {error}
          </div>
        )}

        {editing && (
          <Editor
            key={editing.key}
            initial={editing.draft}
            options={options}
            onSaved={saved}
            onCancel={() => setEditing(null)}
          />
        )}

        {loading ? (
          <p className="text-sm" style={{ color: 'var(--color-text-tertiary)' }} data-testid="routines-loading">
            {t('rotinas.loading')}
          </p>
        ) : rotinas.length === 0 && !error ? (
          <p className="text-sm mb-6" style={{ color: 'var(--color-text-tertiary)' }} data-testid="routines-empty">
            {t('rotinas.empty')}
          </p>
        ) : (
          <ul className="space-y-3 mb-6" data-testid="routines-list">
            {rotinas.map((r) => (
              <RoutineCard
                key={r.id}
                rotina={r}
                options={options}
                busy={busy === r.id}
                onRun={() => void run(r)}
                onEdit={() => edit(draftOf(r))}
                onDelete={() => void remove(r)}
                onToggle={(ativa) => void toggle(r, ativa)}
              />
            ))}
          </ul>
        )}

        {modelos.length > 0 && (
          <section>
            <h2 className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--color-text-tertiary)' }}>
              {t('rotinas.templates')}
            </h2>
            <ul className="space-y-3" data-testid="templates-list">
              {modelos.map((m) => (
                <RoutineCard
                  key={m.id}
                  rotina={m}
                  options={options}
                  template
                  busy={busy === m.id}
                  onRun={() => void run(m)}
                  onEdit={() => edit(draftOf(m, false))}
                />
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}

export default RoutinesPage;
