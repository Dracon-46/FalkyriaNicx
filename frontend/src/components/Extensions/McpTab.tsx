import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, Check, Loader2, Pencil, Plug, Plus, Trash2, X } from 'lucide-react';
import {
  MASK,
  apagarMcp,
  atualizarMcp,
  criarMcp,
  emptyServer,
  listarMcp,
  recarregarMcp,
  serverInput,
  testarMcp,
  type McpList,
  type McpServer,
  type McpServerInput,
  type McpTemplate,
  type McpTest,
  type Trust,
} from '../../lib/extensoes';
import { Badge, Message, buttonClass, card, dangerButton, errorText, field, input, labelClass, primaryButton, secondaryButton } from './ui';

const TRUSTS: Trust[] = ['perguntar', 'livre', 'sempre'];

function envText(env: Record<string, string>): string {
  return Object.entries(env)
    .map(([k, v]) => `${k}=${v}`)
    .join('\n');
}

function parseEnv(text: string): Record<string, string> {
  const env: Record<string, string> = {};
  for (const line of text.split('\n')) {
    const at = line.indexOf('=');
    const key = (at < 0 ? line : line.slice(0, at)).trim();
    if (key) env[key] = at < 0 ? '' : line.slice(at + 1).trim();
  }
  return env;
}

function fromTemplate(tpl: McpTemplate): McpServerInput {
  return {
    ...emptyServer(),
    nome: tpl.chave,
    comando: tpl.comando,
    args: [...tpl.args],
    env: Object.fromEntries(tpl.env.map((k) => [k, ''])),
    confianca: tpl.confianca,
    descricao: tpl.descricao,
  };
}

interface FormProps {
  initial: McpServerInput;
  id: string | null;
  hint: string;
  onSaved: () => void;
  onCancel: () => void;
}

function ServerForm({ initial, id, hint, onSaved, onCancel }: FormProps) {
  const { t } = useTranslation();
  const [s, setS] = useState<McpServerInput>(initial);
  const [args, setArgs] = useState(initial.args.join('\n'));
  const [env, setEnv] = useState(envText(initial.env));
  const [busy, setBusy] = useState<'test' | 'save' | null>(null);
  const [test, setTest] = useState<McpTest | null>(null);
  const [error, setError] = useState('');

  const current = (): McpServerInput => ({
    ...s,
    nome: s.nome.trim(),
    args: args.split('\n').map((a) => a.trim()).filter(Boolean),
    env: parseEnv(env),
  });

  const runTest = async () => {
    setBusy('test');
    setError('');
    setTest(null);
    try {
      setTest(await testarMcp(current(), id ?? undefined));
    } catch (e) {
      setError(errorText(e, t('extensoes.testFailed')));
    } finally {
      setBusy(null);
    }
  };

  const save = async () => {
    setBusy('save');
    setError('');
    try {
      if (id) await atualizarMcp(id, current());
      else await criarMcp(current());
      onSaved();
    } catch (e) {
      setError(errorText(e, t('extensoes.saveFailed')));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="rounded-xl p-4 space-y-3" style={{ ...card, borderColor: 'var(--color-accent)' }} data-testid="mcp-form">
      <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
        {t(id ? 'extensoes.mcp.editTitle' : 'extensoes.mcp.newTitle')}
      </h3>
      {hint && (
        <p className="text-xs" style={{ color: 'var(--color-warning)' }}>
          {hint}
        </p>
      )}
      <div className="grid sm:grid-cols-2 gap-2">
        <label className={labelClass} style={{ color: 'var(--color-text-secondary)' }}>
          {t('extensoes.mcp.name')}
          <input value={s.nome} maxLength={40} onChange={(e) => setS({ ...s, nome: e.target.value })} className={field} style={input} data-testid="mcp-name" />
        </label>
        <label className={labelClass} style={{ color: 'var(--color-text-secondary)' }}>
          {t('extensoes.mcp.type')}
          <select value={s.tipo} onChange={(e) => setS({ ...s, tipo: e.target.value as 'stdio' | 'http' })} className={field} style={input} data-testid="mcp-type">
            <option value="stdio">{t('extensoes.mcp.stdio')}</option>
            <option value="http">{t('extensoes.mcp.http')}</option>
          </select>
        </label>
      </div>
      {s.tipo === 'stdio' ? (
        <>
          <label className={labelClass} style={{ color: 'var(--color-text-secondary)' }}>
            {t('extensoes.mcp.command')}
            <input value={s.comando} onChange={(e) => setS({ ...s, comando: e.target.value })} placeholder="npx" className={`${field} font-mono`} style={input} data-testid="mcp-command" />
          </label>
          <label className={labelClass} style={{ color: 'var(--color-text-secondary)' }}>
            {t('extensoes.mcp.args')}
            <textarea value={args} rows={3} onChange={(e) => setArgs(e.target.value)} className={`${field} font-mono resize-y`} style={input} data-testid="mcp-args" />
          </label>
          <label className={labelClass} style={{ color: 'var(--color-text-secondary)' }}>
            {t('extensoes.mcp.env')}
            <textarea value={env} rows={2} onChange={(e) => setEnv(e.target.value)} placeholder="CHAVE=valor" className={`${field} font-mono resize-y`} style={input} data-testid="mcp-env" />
            <span className="text-[11px]" style={{ color: 'var(--color-text-tertiary)' }}>
              {t('extensoes.mcp.secretHint', { mask: MASK })}
            </span>
          </label>
        </>
      ) : (
        <>
          <label className={labelClass} style={{ color: 'var(--color-text-secondary)' }}>
            {t('extensoes.mcp.url')}
            <input value={s.url} onChange={(e) => setS({ ...s, url: e.target.value })} placeholder="https://" className={field} style={input} data-testid="mcp-url" />
          </label>
          <label className={labelClass} style={{ color: 'var(--color-text-secondary)' }}>
            {t('extensoes.mcp.token')}
            <input type="password" value={s.token} onChange={(e) => setS({ ...s, token: e.target.value })} className={field} style={input} data-testid="mcp-token" autoComplete="off" />
          </label>
        </>
      )}
      <label className={labelClass} style={{ color: 'var(--color-text-secondary)' }}>
        {t('extensoes.mcp.trust')}
        <select value={s.confianca} onChange={(e) => setS({ ...s, confianca: e.target.value as Trust })} className={field} style={input} data-testid="mcp-trust">
          {TRUSTS.map((k) => (
            <option key={k} value={k}>
              {t(`extensoes.mcp.trusts.${k}`)}
            </option>
          ))}
        </select>
      </label>
      {s.tipo === 'stdio' && (
        <p className="text-[11px] flex items-start gap-1" style={{ color: 'var(--color-warning)' }}>
          <AlertTriangle size={11} className="mt-0.5 shrink-0" /> {t('extensoes.mcp.runsProgram')}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => void runTest()} disabled={busy !== null} className={buttonClass} style={secondaryButton} data-testid="mcp-test">
          {busy === 'test' ? <Loader2 size={12} className="animate-spin" /> : <Plug size={12} />} {t('extensoes.mcp.test')}
        </button>
        <button type="button" onClick={() => void save()} disabled={busy !== null} className={buttonClass} style={primaryButton} data-testid="mcp-save">
          {busy === 'save' ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />} {t('extensoes.save')}
        </button>
        <button type="button" onClick={onCancel} disabled={busy !== null} className={buttonClass} style={secondaryButton}>
          <X size={12} /> {t('extensoes.cancel')}
        </button>
      </div>
      {busy === 'test' && (
        <p className="text-xs" role="status" style={{ color: 'var(--color-text-secondary)' }}>
          {t('extensoes.mcp.testing')}
        </p>
      )}
      {test && (
        <div className="text-xs" role="status" data-testid="mcp-test-result" style={{ color: test.ok ? 'var(--color-success)' : 'var(--color-error)' }}>
          {test.ok ? t('extensoes.mcp.testOk', { n: test.ferramentas.length, list: test.ferramentas.map((f) => f.nome).join(', ') }) : t('extensoes.mcp.testError', { error: test.erro })}
        </div>
      )}
      <Message error={error} />
    </div>
  );
}

export function McpTab() {
  const { t } = useTranslation();
  const [data, setData] = useState<McpList | null>(null);
  const [form, setForm] = useState<{ initial: McpServerInput; id: string | null; hint: string; key: number } | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [reloading, setReloading] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await listarMcp());
    } catch (e) {
      setError(errorText(e, t('extensoes.loadFailed')));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  /** Liga as mudanças no chat sem reiniciar o Nicx. */
  const applyChanges = async (message: string) => {
    setForm(null);
    setReloading(true);
    setError('');
    try {
      await recarregarMcp();
      setNotice(message);
    } catch (e) {
      setError(errorText(e, t('extensoes.reloadFailed')));
    } finally {
      setReloading(false);
      await load();
    }
  };

  const open = (initial: McpServerInput, id: string | null = null, hint = '') =>
    setForm((f) => ({ initial, id, hint, key: (f?.key ?? 0) + 1 }));

  const toggle = async (s: McpServer) => {
    try {
      await atualizarMcp(s.id, { ...serverInput(s), ativo: !s.ativo });
      await applyChanges(t(s.ativo ? 'extensoes.mcp.turnedOff' : 'extensoes.mcp.turnedOn', { name: s.nome }));
    } catch (e) {
      setError(errorText(e, t('extensoes.saveFailed')));
    }
  };

  const remove = async (s: McpServer) => {
    if (confirmDelete !== s.id) return setConfirmDelete(s.id);
    setConfirmDelete(null);
    try {
      await apagarMcp(s.id);
      await applyChanges(t('extensoes.mcp.deleted', { name: s.nome }));
    } catch (e) {
      setError(errorText(e, t('extensoes.deleteFailed')));
    }
  };

  if (!data) return <Message error={error} />;

  return (
    <div className="space-y-5">
      <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
        {t('extensoes.mcp.intro')}
      </p>
      {!data.npx && (
        <p className="text-xs flex items-start gap-1" style={{ color: 'var(--color-warning)' }} data-testid="mcp-no-npx">
          <AlertTriangle size={12} className="mt-0.5 shrink-0" /> {t('extensoes.mcp.noNpx')}
        </p>
      )}
      <Message error={error} notice={notice} />
      {reloading && (
        <p className="text-xs flex items-center gap-1.5" role="status" style={{ color: 'var(--color-text-secondary)' }}>
          <Loader2 size={12} className="animate-spin" /> {t('extensoes.mcp.reloading')}
        </p>
      )}
      {form && (
        <ServerForm
          key={form.key}
          initial={form.initial}
          id={form.id}
          hint={form.hint}
          onSaved={() => void applyChanges(t('extensoes.mcp.saved'))}
          onCancel={() => setForm(null)}
        />
      )}

      <section>
        <div className="flex items-center justify-between gap-2 mb-2">
          <h2 className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
            {t('extensoes.mcp.mine')}
          </h2>
          <button type="button" onClick={() => open(emptyServer())} className={buttonClass} style={secondaryButton} data-testid="mcp-new">
            <Plus size={12} /> {t('extensoes.mcp.custom')}
          </button>
        </div>
        {data.servidores.length === 0 ? (
          <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }} data-testid="mcp-empty">
            {t('extensoes.mcp.empty')}
          </p>
        ) : (
          <ul className="space-y-2">
            {data.servidores.map((s) => {
              const state = s.ativo ? (s.situacao?.estado ?? 'pendente') : 'desligado';
              const tone = state === 'ligado' ? 'ok' : state === 'erro' ? 'error' : 'neutral';
              return (
                <li key={s.id} className="rounded-xl p-3" style={card} data-testid={`mcp-${s.id}`}>
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-sm font-semibold flex items-center gap-1.5 flex-wrap" style={{ color: 'var(--color-text)' }}>
                        {s.nome} <Badge tone={tone}>{t(`extensoes.mcp.states.${state}`)}</Badge>
                        <Badge>{t(`extensoes.mcp.trusts.${s.confianca}`)}</Badge>
                        {s.pacote && <Badge>{t('extensoes.fromPack', { id: s.pacote })}</Badge>}
                      </div>
                      <div className="text-xs mt-0.5 font-mono break-all" style={{ color: 'var(--color-text-tertiary)' }}>
                        {s.tipo === 'http' ? s.url : [s.comando, ...s.args].join(' ')}
                      </div>
                      {s.situacao?.ferramentas.length ? (
                        <div className="text-xs mt-1 break-words" style={{ color: 'var(--color-text-secondary)' }}>
                          {t('extensoes.mcp.tools', { list: s.situacao.ferramentas.join(', ') })}
                        </div>
                      ) : null}
                      {state === 'erro' && s.situacao?.erro && (
                        <div className="text-xs mt-1" style={{ color: 'var(--color-error)' }}>
                          {s.situacao.erro}
                        </div>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      <button type="button" onClick={() => void toggle(s)} disabled={reloading} className={buttonClass} style={s.ativo ? primaryButton : secondaryButton} aria-pressed={s.ativo} data-testid={`mcp-toggle-${s.id}`}>
                        {t(s.ativo ? 'extensoes.on' : 'extensoes.off')}
                      </button>
                      <button type="button" onClick={() => open(serverInput(s), s.id)} className={buttonClass} style={secondaryButton} data-testid={`mcp-edit-${s.id}`}>
                        <Pencil size={12} /> {t('extensoes.edit')}
                      </button>
                      <button type="button" onClick={() => void remove(s)} disabled={reloading} className={buttonClass} style={confirmDelete === s.id ? dangerButton : secondaryButton} data-testid={`mcp-delete-${s.id}`}>
                        <Trash2 size={12} /> {t(confirmDelete === s.id ? 'extensoes.confirm' : 'extensoes.delete')}
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
          {t('extensoes.mcp.catalog')}
        </h2>
        <ul className="grid sm:grid-cols-2 gap-2">
          {data.catalogo.map((tpl) => (
            <li key={tpl.chave} className="rounded-xl p-3 flex items-start justify-between gap-2" style={card} data-testid={`mcp-template-${tpl.chave}`}>
              <div className="min-w-0">
                <div className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                  {tpl.chave}
                </div>
                <div className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                  {t(`extensoes.mcp.catalogItems.${tpl.chave}`, { defaultValue: tpl.descricao })}
                </div>
                {tpl.env.length > 0 && (
                  <div className="text-[11px] mt-0.5" style={{ color: 'var(--color-text-tertiary)' }}>
                    {t('extensoes.mcp.needsKey', { list: tpl.env.join(', ') })}
                  </div>
                )}
              </div>
              <button
                type="button"
                onClick={() => open(fromTemplate(tpl), null, tpl.pede_args ? t(`extensoes.mcp.asks.${tpl.pede_args}`) : '')}
                className={buttonClass}
                style={secondaryButton}
                data-testid={`mcp-add-${tpl.chave}`}
              >
                <Plus size={12} /> {t('extensoes.add')}
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
