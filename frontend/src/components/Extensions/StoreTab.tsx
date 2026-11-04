import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { BadgeCheck, Download, Loader2, RefreshCw, Search, Store } from 'lucide-react';
import { instalarDaLoja, listarLoja, previaLoja, type PackPreview, type StorePack } from '../../lib/extensoes';
import { Items, Permissions } from './PacksTab';
import { Badge, Message, buttonClass, card, errorText, input, primaryButton, secondaryButton } from './ui';

export function StoreTab() {
  const { t } = useTranslation();
  const [packs, setPacks] = useState<StorePack[] | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');
  const [open, setOpen] = useState<{ id: string; preview: PackPreview } | null>(null);
  const [withMcp, setWithMcp] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError('');
    try {
      setPacks(await listarLoja());
    } catch (e) {
      setPacks([]);
      setError(errorText(e, t('extensoes.loadFailed')));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const categories = useMemo(() => [...new Set((packs ?? []).map((p) => p.categoria))].sort(), [packs]);
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (packs ?? []).filter(
      (p) => (!category || p.categoria === category) && (!q || `${p.nome} ${p.descricao} ${p.autor}`.toLowerCase().includes(q)),
    );
  }, [packs, query, category]);

  const details = async (id: string) => {
    setBusy(id);
    setError('');
    setNotice('');
    try {
      setOpen({ id, preview: await previaLoja(id) });
      setWithMcp(false);
    } catch (e) {
      setError(errorText(e, t('extensoes.previewFailed')));
    } finally {
      setBusy(null);
    }
  };

  const install = async () => {
    if (!open) return;
    setBusy(open.id);
    setError('');
    try {
      const result = await instalarDaLoja(open.id, withMcp);
      setNotice(t('extensoes.packs.installed', { name: open.preview.nome }));
      if (result.pulados.length) setError(t('extensoes.packs.skipped', { list: result.pulados.join('\n') }));
      setOpen(null);
      await load();
    } catch (e) {
      setError(errorText(e, t('extensoes.installFailed')));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-4">
      <p className="text-xs flex items-start gap-1.5" style={{ color: 'var(--color-text-secondary)' }}>
        <BadgeCheck size={13} className="mt-0.5 shrink-0" style={{ color: 'var(--color-accent)' }} /> {t('extensoes.store.intro')}
      </p>
      <div className="flex flex-col sm:flex-row gap-2">
        <label className="flex-1 flex items-center gap-1.5 px-3 py-1.5 rounded-lg" style={input}>
          <Search size={13} style={{ color: 'var(--color-text-tertiary)' }} />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t('extensoes.store.search')} aria-label={t('extensoes.store.search')} className="flex-1 min-w-0 bg-transparent text-sm outline-none" style={{ color: 'var(--color-text)' }} data-testid="store-search" />
        </label>
        <button type="button" onClick={() => void load()} className={buttonClass} style={secondaryButton} data-testid="store-refresh">
          <RefreshCw size={12} /> {t('extensoes.store.refresh')}
        </button>
      </div>
      {categories.length > 1 && (
        <div className="flex flex-wrap gap-1.5">
          {['', ...categories].map((c) => (
            <button key={c || 'all'} type="button" onClick={() => setCategory(c)} className="px-2.5 py-1 rounded-full text-xs cursor-pointer" style={c === category ? primaryButton : secondaryButton} data-testid={`store-category-${c || 'all'}`}>
              {c ? t(`extensoes.store.categories.${c}`, { defaultValue: c }) : t('extensoes.store.all')}
            </button>
          ))}
        </div>
      )}
      <Message error={error} notice={notice} />
      {packs === null && (
        <p className="text-xs flex items-center gap-1.5" style={{ color: 'var(--color-text-secondary)' }}>
          <Loader2 size={12} className="animate-spin" /> {t('extensoes.store.loading')}
        </p>
      )}
      {packs !== null && packs.length === 0 && !error && (
        <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }} data-testid="store-empty">
          {t('extensoes.store.empty')}
        </p>
      )}
      <ul className="grid sm:grid-cols-2 gap-2">
        {shown.map((p) => (
          <li key={p.id} className="rounded-xl p-3 flex flex-col gap-2" style={card} data-testid={`store-${p.id}`}>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="text-sm font-semibold flex items-center gap-1.5" style={{ color: 'var(--color-text)' }}>
                  <Store size={13} /> {p.nome}
                </div>
                <div className="text-xs mt-0.5" style={{ color: 'var(--color-text-secondary)' }}>
                  {p.descricao}
                </div>
                <div className="text-[11px] mt-1" style={{ color: 'var(--color-text-tertiary)' }}>
                  {t('extensoes.store.meta', { author: p.autor, version: p.versao, downloads: p.downloads })}
                </div>
              </div>
              {p.atualizacao ? <Badge tone="warn">{t('extensoes.store.update')}</Badge> : p.versao_instalada ? <Badge tone="ok">{t('extensoes.packs.isInstalled')}</Badge> : null}
            </div>
            <button type="button" onClick={() => void details(p.id)} disabled={busy !== null} className={`${buttonClass} self-start mt-auto`} style={p.atualizacao || !p.versao_instalada ? primaryButton : secondaryButton} data-testid={`store-open-${p.id}`}>
              {busy === p.id ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
              {t(p.atualizacao ? 'extensoes.packs.reinstall' : p.versao_instalada ? 'extensoes.store.details' : 'extensoes.packs.install')}
            </button>
            {open?.id === p.id && (
              <div className="rounded-lg p-3 space-y-2" style={{ border: '1px solid var(--color-accent)' }} data-testid="store-preview">
                <div className="text-xs flex items-center gap-1" style={{ color: 'var(--color-success)' }}>
                  <BadgeCheck size={12} /> {t('extensoes.store.verified')}
                </div>
                <Items preview={open.preview} />
                <div className="text-xs font-medium" style={{ color: 'var(--color-text)' }}>
                  {t('extensoes.packs.perm.title')}
                </div>
                <Permissions preview={open.preview} />
                {open.preview.itens.mcp.length > 0 && (
                  <label className="flex items-start gap-2 text-xs cursor-pointer" style={{ color: 'var(--color-text)' }}>
                    <input type="checkbox" className="mt-0.5" checked={withMcp} onChange={(e) => setWithMcp(e.target.checked)} data-testid="store-with-mcp" />
                    <span>{t('extensoes.packs.withMcp')}</span>
                  </label>
                )}
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={() => void install()} disabled={busy !== null} className={buttonClass} style={primaryButton} data-testid="store-install">
                    {busy === p.id ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />} {t('extensoes.packs.install')}
                  </button>
                  <button type="button" onClick={() => setOpen(null)} className={buttonClass} style={secondaryButton}>
                    {t('extensoes.cancel')}
                  </button>
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
