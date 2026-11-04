import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, Download, Loader2, Package, Trash2, Upload } from 'lucide-react';
import {
  baixarPacote,
  desinstalarPacote,
  exportarPacote,
  instalarPacote,
  listarHabilidades,
  listarMcp,
  listarPacotes,
  previaPacote,
  type InstalledPack,
  type PackPreview,
} from '../../lib/extensoes';
import { listarAssistentes } from '../../lib/assistentes';
import { listarRotinas } from '../../lib/rotinas';
import { Badge, Message, buttonClass, card, dangerButton, errorText, field, input, labelClass, primaryButton, secondaryButton } from './ui';

function Items({ preview }: { preview: PackPreview }) {
  const { t } = useTranslation();
  const groups = (['assistentes', 'rotinas', 'habilidades', 'mcp'] as const).filter((k) => preview.itens[k].length);
  return (
    <ul className="text-xs space-y-0.5" style={{ color: 'var(--color-text-secondary)' }}>
      {groups.map((k) => (
        <li key={k}>
          <span style={{ color: 'var(--color-text)' }}>{t(`extensoes.packs.kinds.${k}`)}:</span> {preview.itens[k].join(', ')}
        </li>
      ))}
    </ul>
  );
}

/** O que o pacote pode fazer: o usuário vê antes de instalar. */
function Permissions({ preview }: { preview: PackPreview }) {
  const { t } = useTranslation();
  const p = preview.permissoes;
  const lines: { key: string; text: string; warn?: boolean }[] = [];
  if (p.comandos.length) lines.push({ key: 'commands', text: t('extensoes.packs.perm.commands', { list: p.comandos.join(' · ') }), warn: true });
  if (p.enderecos.length) lines.push({ key: 'urls', text: t('extensoes.packs.perm.urls', { list: p.enderecos.join(' · ') }) });
  if (p.segredos.length) lines.push({ key: 'secrets', text: t('extensoes.packs.perm.secrets', { list: p.segredos.join(', ') }) });
  if (p.todas_as_ferramentas) lines.push({ key: 'all', text: t('extensoes.packs.perm.allTools'), warn: true });
  else if (p.ferramentas.length) lines.push({ key: 'tools', text: t('extensoes.packs.perm.tools', { list: p.ferramentas.join(', ') }) });
  if (p.rotinas_com_horario.length) lines.push({ key: 'sched', text: t('extensoes.packs.perm.scheduled', { list: p.rotinas_com_horario.join(', ') }) });
  if (!lines.length) lines.push({ key: 'none', text: t('extensoes.packs.perm.none') });
  return (
    <ul className="text-xs space-y-0.5 mt-1" data-testid={`pack-perms-${preview.id}`}>
      {lines.map((l) => (
        <li key={l.key} className="flex items-start gap-1 break-words" style={{ color: l.warn ? 'var(--color-warning)' : 'var(--color-text-secondary)' }}>
          {l.warn && <AlertTriangle size={11} className="mt-0.5 shrink-0" />} <span className="min-w-0">{l.text}</span>
        </li>
      ))}
    </ul>
  );
}

function ExportForm({ onError }: { onError: (e: string) => void }) {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const [meta, setMeta] = useState({ id: '', nome: '', descricao: '', autor: '' });
  const [options, setOptions] = useState<{ key: 'assistentes' | 'rotinas' | 'habilidades' | 'mcp'; id: string; label: string }[]>([]);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setOpen(true);
    try {
      const [a, r, h, m] = await Promise.all([
        listarAssistentes(i18n.language),
        listarRotinas(i18n.language),
        listarHabilidades(),
        listarMcp(),
      ]);
      setOptions([
        ...a.assistentes.map((x) => ({ key: 'assistentes' as const, id: x.id, label: x.nome })),
        ...r.rotinas.map((x) => ({ key: 'rotinas' as const, id: x.id, label: x.nome })),
        ...h.habilidades.map((x) => ({ key: 'habilidades' as const, id: x.nome, label: x.titulo })),
        ...m.servidores.map((x) => ({ key: 'mcp' as const, id: x.id, label: x.nome })),
      ]);
    } catch (e) {
      onError(errorText(e, t('extensoes.loadFailed')));
    }
  };

  const toggle = (k: string) =>
    setChosen((c) => {
      const next = new Set(c);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });

  const pick = (key: string) => options.filter((o) => o.key === key && chosen.has(`${o.key}:${o.id}`)).map((o) => o.id);

  const run = async () => {
    setBusy(true);
    try {
      const id = meta.id.trim() || meta.nome.trim().toLowerCase().normalize('NFKD').replace(/[^\w\s-]/g, '').trim().replace(/[\s_]+/g, '-').slice(0, 40);
      baixarPacote(
        await exportarPacote({
          id,
          nome: meta.nome.trim(),
          descricao: meta.descricao,
          autor: meta.autor,
          versao: '1.0.0',
          assistentes: pick('assistentes'),
          rotinas: pick('rotinas'),
          habilidades: pick('habilidades'),
          mcp: pick('mcp'),
        }),
      );
    } catch (e) {
      onError(errorText(e, t('extensoes.exportFailed')));
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button type="button" onClick={() => void load()} className={buttonClass} style={secondaryButton} data-testid="pack-export-open">
        <Download size={12} /> {t('extensoes.packs.export.open')}
      </button>
    );
  }
  return (
    <div className="rounded-xl p-4 space-y-3" style={card} data-testid="pack-export">
      <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
        {t('extensoes.packs.export.title')}
      </h3>
      <div className="grid sm:grid-cols-2 gap-2">
        {(['nome', 'autor'] as const).map((k) => (
          <label key={k} className={labelClass} style={{ color: 'var(--color-text-secondary)' }}>
            {t(`extensoes.packs.export.${k}`)}
            <input value={meta[k]} maxLength={60} onChange={(e) => setMeta({ ...meta, [k]: e.target.value })} className={field} style={input} data-testid={`pack-export-${k}`} />
          </label>
        ))}
      </div>
      <label className={labelClass} style={{ color: 'var(--color-text-secondary)' }}>
        {t('extensoes.packs.export.description')}
        <input value={meta.descricao} maxLength={300} onChange={(e) => setMeta({ ...meta, descricao: e.target.value })} className={field} style={input} />
      </label>
      {options.length === 0 ? (
        <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
          {t('extensoes.packs.export.nothing')}
        </p>
      ) : (
        <div className="grid sm:grid-cols-2 gap-1">
          {options.map((o) => (
            <label key={`${o.key}:${o.id}`} className="flex items-center gap-1.5 text-xs cursor-pointer min-w-0" style={{ color: 'var(--color-text)' }}>
              <input type="checkbox" checked={chosen.has(`${o.key}:${o.id}`)} onChange={() => toggle(`${o.key}:${o.id}`)} data-testid={`pack-export-item-${o.key}-${o.id}`} />
              <span className="truncate">
                {o.label} <span style={{ color: 'var(--color-text-tertiary)' }}>· {t(`extensoes.packs.kinds.${o.key}`)}</span>
              </span>
            </label>
          ))}
        </div>
      )}
      <p className="text-[11px]" style={{ color: 'var(--color-text-tertiary)' }}>
        {t('extensoes.packs.export.noSecrets')}
      </p>
      <button type="button" onClick={() => void run()} disabled={busy || !meta.nome.trim() || chosen.size === 0} className={buttonClass} style={primaryButton} data-testid="pack-export-run">
        {busy ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />} {t('extensoes.packs.export.run')}
      </button>
    </div>
  );
}

export function PacksTab() {
  const { t, i18n } = useTranslation();
  const [ready, setReady] = useState<PackPreview[]>([]);
  const [installed, setInstalled] = useState<InstalledPack[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [imported, setImported] = useState<{ preview: PackPreview; content: string } | null>(null);
  const [withMcp, setWithMcp] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const data = await listarPacotes(i18n.language);
      setReady(data.prontos);
      setInstalled(data.instalados);
    } catch (e) {
      setError(errorText(e, t('extensoes.loadFailed')));
    }
  }, [i18n.language, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const install = async (pedido: { pronto?: string; conteudo?: string; com_mcp?: boolean }, name: string) => {
    setBusy(pedido.pronto ?? 'import');
    setError('');
    setNotice('');
    try {
      const result = await instalarPacote({ ...pedido, idioma: i18n.language });
      setNotice(t('extensoes.packs.installed', { name }));
      if (result.pulados.length) setError(t('extensoes.packs.skipped', { list: result.pulados.join('\n') }));
      setImported(null);
      await load();
    } catch (e) {
      setError(errorText(e, t('extensoes.installFailed')));
    } finally {
      setBusy(null);
    }
  };

  const remove = async (id: string, name: string) => {
    if (confirmRemove !== id) return setConfirmRemove(id);
    setConfirmRemove(null);
    setBusy(id);
    setError('');
    try {
      await desinstalarPacote(id);
      setNotice(t('extensoes.packs.removed', { name }));
      await load();
    } catch (e) {
      setError(errorText(e, t('extensoes.deleteFailed')));
    } finally {
      setBusy(null);
    }
  };

  const readFile = async (file: File) => {
    setError('');
    setNotice('');
    try {
      const content = await file.text();
      setImported({ preview: await previaPacote(content), content });
      setWithMcp(false);
    } catch (e) {
      setError(errorText(e, t('extensoes.previewFailed')));
    }
  };

  const installedIds = new Set(installed.map((p) => p.id));

  return (
    <div className="space-y-5">
      <Message error={error} notice={notice} />

      <section>
        <h2 className="text-sm font-semibold mb-2" style={{ color: 'var(--color-text)' }}>
          {t('extensoes.packs.ready')}
        </h2>
        <ul className="grid sm:grid-cols-2 gap-2">
          {ready.map((p) => {
            const isInstalled = installedIds.has(p.id);
            return (
              <li key={p.id} className="rounded-xl p-3 flex flex-col gap-2" style={card} data-testid={`pack-${p.id}`}>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-sm font-semibold flex items-center gap-1.5" style={{ color: 'var(--color-text)' }}>
                      <Package size={13} /> {p.nome}
                    </div>
                    <div className="text-xs mt-0.5" style={{ color: 'var(--color-text-secondary)' }}>
                      {p.descricao}
                    </div>
                  </div>
                  {isInstalled && <Badge tone="ok">{t('extensoes.packs.isInstalled')}</Badge>}
                </div>
                <Items preview={p} />
                <div className="flex flex-wrap gap-1.5 mt-auto">
                  <button
                    type="button"
                    onClick={() => void install({ pronto: p.id }, p.nome)}
                    disabled={busy !== null}
                    className={buttonClass}
                    style={isInstalled ? secondaryButton : primaryButton}
                    data-testid={`pack-install-${p.id}`}
                  >
                    {busy === p.id ? <Loader2 size={12} className="animate-spin" /> : <Package size={12} />}
                    {t(isInstalled ? 'extensoes.packs.reinstall' : 'extensoes.packs.install')}
                  </button>
                  {isInstalled && (
                    <button type="button" onClick={() => void remove(p.id, p.nome)} disabled={busy !== null} className={buttonClass} style={confirmRemove === p.id ? dangerButton : secondaryButton} data-testid={`pack-remove-${p.id}`}>
                      <Trash2 size={12} /> {t(confirmRemove === p.id ? 'extensoes.confirm' : 'extensoes.packs.remove')}
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
        <p className="text-[11px] mt-2" style={{ color: 'var(--color-text-tertiary)' }}>
          {t('extensoes.packs.readyHint')}
        </p>
      </section>

      <section className="rounded-xl p-4 space-y-2" style={card}>
        <h2 className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
          {t('extensoes.packs.import.title')}
        </h2>
        <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          {t('extensoes.packs.import.hint')}
        </p>
        <input
          ref={fileRef}
          type="file"
          accept=".json,application/json"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void readFile(file);
            e.target.value = '';
          }}
          data-testid="pack-file"
        />
        <button type="button" onClick={() => fileRef.current?.click()} className={buttonClass} style={secondaryButton} data-testid="pack-import">
          <Upload size={12} /> {t('extensoes.packs.import.choose')}
        </button>
        {imported && (
          <div className="rounded-lg p-3 space-y-2" style={{ border: '1px solid var(--color-accent)' }} data-testid="pack-preview">
            <div className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
              {imported.preview.nome} {imported.preview.versao && <span className="text-xs font-normal">v{imported.preview.versao}</span>}
            </div>
            {imported.preview.autor && (
              <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                {t('extensoes.packs.by', { author: imported.preview.autor })}
              </div>
            )}
            <Items preview={imported.preview} />
            <div className="text-xs font-medium" style={{ color: 'var(--color-text)' }}>
              {t('extensoes.packs.perm.title')}
            </div>
            <Permissions preview={imported.preview} />
            {imported.preview.problemas.length > 0 && (
              <div className="text-xs whitespace-pre-line" style={{ color: 'var(--color-warning)' }}>
                {t('extensoes.packs.problems', { list: imported.preview.problemas.join('\n') })}
              </div>
            )}
            {imported.preview.itens.mcp.length > 0 && (
              <label className="flex items-start gap-2 text-xs cursor-pointer" style={{ color: 'var(--color-text)' }}>
                <input type="checkbox" className="mt-0.5" checked={withMcp} onChange={(e) => setWithMcp(e.target.checked)} data-testid="pack-with-mcp" />
                <span>{t('extensoes.packs.withMcp')}</span>
              </label>
            )}
            {imported.preview.instalado && (
              <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                {t('extensoes.packs.willUpdate', { version: imported.preview.versao_instalada || '?' })}
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => void install({ conteudo: imported.content, com_mcp: withMcp }, imported.preview.nome)} disabled={busy !== null} className={buttonClass} style={primaryButton} data-testid="pack-install-imported">
                {busy === 'import' ? <Loader2 size={12} className="animate-spin" /> : <Package size={12} />} {t('extensoes.packs.install')}
              </button>
              <button type="button" onClick={() => setImported(null)} className={buttonClass} style={secondaryButton}>
                {t('extensoes.cancel')}
              </button>
            </div>
          </div>
        )}
      </section>

      {installed.filter((p) => !p.pronto).length > 0 && (
        <section>
          <h2 className="text-sm font-semibold mb-2" style={{ color: 'var(--color-text)' }}>
            {t('extensoes.packs.imported')}
          </h2>
          <ul className="space-y-2">
            {installed
              .filter((p) => !p.pronto)
              .map((p) => (
                <li key={p.id} className="rounded-xl p-3 flex flex-wrap items-center justify-between gap-2" style={card} data-testid={`installed-${p.id}`}>
                  <span className="text-sm" style={{ color: 'var(--color-text)' }}>
                    {p.nome} {p.versao && <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>v{p.versao}</span>}
                  </span>
                  <button type="button" onClick={() => void remove(p.id, p.nome)} disabled={busy !== null} className={buttonClass} style={confirmRemove === p.id ? dangerButton : secondaryButton} data-testid={`pack-remove-${p.id}`}>
                    <Trash2 size={12} /> {t(confirmRemove === p.id ? 'extensoes.confirm' : 'extensoes.packs.remove')}
                  </button>
                </li>
              ))}
          </ul>
        </section>
      )}

      <ExportForm onError={setError} />
    </div>
  );
}
