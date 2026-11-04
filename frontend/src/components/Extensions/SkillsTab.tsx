import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, Check, GitBranch, Loader2, Pencil, Plus, Trash2, Upload, X } from 'lucide-react';
import {
  apagarHabilidade,
  atualizarHabilidade,
  criarHabilidade,
  importarHabilidadesZip,
  instalarHabilidadesGithub,
  ligarHabilidade,
  listarHabilidades,
  recarregarHabilidades,
  type Skill,
  type SkillImport,
  type SkillInput,
} from '../../lib/extensoes';
import { Badge, Message, buttonClass, card, dangerButton, errorText, field, input, labelClass, primaryButton, secondaryButton } from './ui';

function SkillForm({ initial, name, onSaved, onCancel }: { initial: SkillInput; name: string | null; onSaved: (s: Skill) => void; onCancel: () => void }) {
  const { t } = useTranslation();
  const [s, setS] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const save = async () => {
    if (!s.titulo.trim() || !s.descricao.trim() || !s.instrucoes.trim()) return setError(t('extensoes.skills.needAll'));
    setBusy(true);
    setError('');
    try {
      onSaved(name ? await atualizarHabilidade(name, s) : await criarHabilidade(s));
    } catch (e) {
      setError(errorText(e, t('extensoes.saveFailed')));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-xl p-4 space-y-3" style={{ ...card, borderColor: 'var(--color-accent)' }} data-testid="skill-form">
      <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
        {t(name ? 'extensoes.skills.editTitle' : 'extensoes.skills.newTitle')}
      </h3>
      <label className={labelClass} style={{ color: 'var(--color-text-secondary)' }}>
        {t('extensoes.skills.title')}
        <input value={s.titulo} maxLength={60} onChange={(e) => setS({ ...s, titulo: e.target.value })} placeholder={t('extensoes.skills.titlePlaceholder')} className={field} style={input} data-testid="skill-title" />
      </label>
      <label className={labelClass} style={{ color: 'var(--color-text-secondary)' }}>
        {t('extensoes.skills.when')}
        <input value={s.descricao} maxLength={1024} onChange={(e) => setS({ ...s, descricao: e.target.value })} placeholder={t('extensoes.skills.whenPlaceholder')} className={field} style={input} data-testid="skill-when" />
      </label>
      <label className={labelClass} style={{ color: 'var(--color-text-secondary)' }}>
        {t('extensoes.skills.instructions')}
        <textarea value={s.instrucoes} rows={8} maxLength={20000} onChange={(e) => setS({ ...s, instrucoes: e.target.value })} placeholder={t('extensoes.skills.instructionsPlaceholder')} className={`${field} resize-y`} style={input} data-testid="skill-instructions" />
      </label>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => void save()} disabled={busy} className={buttonClass} style={primaryButton} data-testid="skill-save">
          {busy ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />} {t('extensoes.save')}
        </button>
        <button type="button" onClick={onCancel} disabled={busy} className={buttonClass} style={secondaryButton}>
          <X size={12} /> {t('extensoes.cancel')}
        </button>
      </div>
      <Message error={error} />
    </div>
  );
}

export function SkillsTab() {
  const { t } = useTranslation();
  const [skills, setSkills] = useState<Skill[] | null>(null);
  const [form, setForm] = useState<{ initial: SkillInput; name: string | null; key: number } | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [github, setGithub] = useState('');
  const [pending, setPending] = useState<{ kind: 'zip'; file: File } | { kind: 'github'; url: string } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      setSkills((await listarHabilidades()).habilidades);
    } catch (e) {
      setError(errorText(e, t('extensoes.loadFailed')));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  /** Liga as mudanças no chat; a lista recarrega junto. */
  const applied = async (message: string) => {
    setNotice(message);
    try {
      await recarregarHabilidades();
    } catch (e) {
      setError(errorText(e, t('extensoes.reloadFailed')));
    }
    await load();
  };

  const report = async (results: SkillImport[], retry: typeof pending) => {
    const ok = results.filter((r) => r.ok).map((r) => r.nome);
    const dangerous = results.filter((r) => r.pede_confirmacao);
    const failed = results.filter((r) => !r.ok && !r.pede_confirmacao);
    setPending(dangerous.length ? retry : null);
    if (dangerous.length) setError(t('extensoes.skills.dangerous', { list: dangerous.map((r) => `${r.nome} (${(r.perigosas ?? []).join(', ')})`).join('; ') }));
    else if (failed.length) setError(t('extensoes.skills.importErrors', { list: failed.map((r) => `${r.nome}: ${(r.avisos ?? []).join(' ')}`).join('\n') }));
    if (ok.length) await applied(t('extensoes.skills.imported', { list: ok.join(', ') }));
  };

  const importZip = async (file: File, confirm = false) => {
    setBusy('zip');
    setError('');
    setNotice('');
    try {
      await report(await importarHabilidadesZip(file, confirm), { kind: 'zip', file });
    } catch (e) {
      setError(errorText(e, t('extensoes.importFailed')));
    } finally {
      setBusy(null);
    }
  };

  const importGithub = async (url: string, confirm = false) => {
    setBusy('github');
    setError('');
    setNotice('');
    try {
      await report(await instalarHabilidadesGithub(url, confirm), { kind: 'github', url });
      if (!confirm) setGithub('');
    } catch (e) {
      setError(errorText(e, t('extensoes.importFailed')));
    } finally {
      setBusy(null);
    }
  };

  const confirmPending = () => {
    if (!pending) return;
    if (pending.kind === 'zip') void importZip(pending.file, true);
    else void importGithub(pending.url, true);
  };

  const toggle = async (s: Skill) => {
    try {
      await ligarHabilidade(s.nome, !s.ativa);
      await applied(t(s.ativa ? 'extensoes.skills.turnedOff' : 'extensoes.skills.turnedOn', { name: s.titulo }));
    } catch (e) {
      setError(errorText(e, t('extensoes.saveFailed')));
    }
  };

  const remove = async (s: Skill) => {
    if (confirmDelete !== s.nome) return setConfirmDelete(s.nome);
    setConfirmDelete(null);
    try {
      await apagarHabilidade(s.nome);
      await applied(t('extensoes.skills.deleted', { name: s.titulo }));
    } catch (e) {
      setError(errorText(e, t('extensoes.deleteFailed')));
    }
  };

  const open = (initial: SkillInput, name: string | null = null) => setForm((f) => ({ initial, name, key: (f?.key ?? 0) + 1 }));

  return (
    <div className="space-y-5">
      <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
        {t('extensoes.skills.intro')}
      </p>
      <Message error={error} notice={notice} />
      {pending && (
        <button type="button" onClick={confirmPending} disabled={busy !== null} className={buttonClass} style={dangerButton} data-testid="skill-confirm-dangerous">
          <AlertTriangle size={12} /> {t('extensoes.skills.installAnyway')}
        </button>
      )}
      {form && (
        <SkillForm
          key={form.key}
          initial={form.initial}
          name={form.name}
          onSaved={(s) => {
            setForm(null);
            void applied(t('extensoes.skills.saved', { name: s.titulo }));
          }}
          onCancel={() => setForm(null)}
        />
      )}

      <section>
        <div className="flex items-center justify-between gap-2 mb-2">
          <h2 className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
            {t('extensoes.skills.mine')}
          </h2>
          <button type="button" onClick={() => open({ titulo: '', descricao: '', instrucoes: '' })} className={buttonClass} style={secondaryButton} data-testid="skill-new">
            <Plus size={12} /> {t('extensoes.skills.create')}
          </button>
        </div>
        {skills && skills.length === 0 && (
          <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }} data-testid="skill-empty">
            {t('extensoes.skills.empty')}
          </p>
        )}
        <ul className="space-y-2">
          {(skills ?? []).map((s) => (
            <li key={s.nome} className="rounded-xl p-3" style={card} data-testid={`skill-${s.nome}`}>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="text-sm font-semibold flex items-center gap-1.5 flex-wrap" style={{ color: 'var(--color-text)' }}>
                    {s.titulo}
                    <Badge>{s.origem.startsWith('pacote:') ? t('extensoes.fromPack', { id: s.origem.slice(7) }) : t(`extensoes.skills.origins.${s.origem}`, { defaultValue: s.origem })}</Badge>
                    {s.perigosas.length > 0 && <Badge tone="warn">{s.perigosas.join(', ')}</Badge>}
                  </div>
                  <div className="text-xs mt-0.5 break-words" style={{ color: 'var(--color-text-secondary)' }}>
                    {s.descricao}
                  </div>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  <button type="button" onClick={() => void toggle(s)} className={buttonClass} style={s.ativa ? primaryButton : secondaryButton} aria-pressed={s.ativa} data-testid={`skill-toggle-${s.nome}`}>
                    {t(s.ativa ? 'extensoes.on' : 'extensoes.off')}
                  </button>
                  {s.editavel && (
                    <button type="button" onClick={() => open({ titulo: s.titulo, descricao: s.descricao, instrucoes: s.instrucoes }, s.nome)} className={buttonClass} style={secondaryButton} data-testid={`skill-edit-${s.nome}`}>
                      <Pencil size={12} /> {t('extensoes.edit')}
                    </button>
                  )}
                  <button type="button" onClick={() => void remove(s)} className={buttonClass} style={confirmDelete === s.nome ? dangerButton : secondaryButton} data-testid={`skill-delete-${s.nome}`}>
                    <Trash2 size={12} /> {t(confirmDelete === s.nome ? 'extensoes.confirm' : 'extensoes.delete')}
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-xl p-4 space-y-2" style={card}>
        <h2 className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
          {t('extensoes.skills.importTitle')}
        </h2>
        <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          {t('extensoes.skills.importHint')}
        </p>
        <input
          ref={fileRef}
          type="file"
          accept=".zip,application/zip"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void importZip(file);
            e.target.value = '';
          }}
          data-testid="skill-zip"
        />
        <div className="flex flex-col sm:flex-row gap-2">
          <button type="button" onClick={() => fileRef.current?.click()} disabled={busy !== null} className={buttonClass} style={secondaryButton} data-testid="skill-import-zip">
            {busy === 'zip' ? <Loader2 size={12} className="animate-spin" /> : <Upload size={12} />} {t('extensoes.skills.chooseZip')}
          </button>
          <div className="flex-1 flex items-center gap-1.5 min-w-0">
            <input value={github} onChange={(e) => setGithub(e.target.value)} placeholder="https://github.com/dono/repositorio" aria-label={t('extensoes.skills.github')} className="flex-1 min-w-0 px-3 py-1.5 rounded-lg text-sm" style={input} data-testid="skill-github" />
            <button type="button" onClick={() => void importGithub(github.trim())} disabled={busy !== null || !github.trim()} className={buttonClass} style={secondaryButton} data-testid="skill-github-install">
              {busy === 'github' ? <Loader2 size={12} className="animate-spin" /> : <GitBranch size={12} />} {t('extensoes.skills.install')}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
