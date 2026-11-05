import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowUpCircle, CheckCircle2, Loader2, RefreshCw, Sparkles, Terminal } from 'lucide-react';
import {
  atualizarEstado,
  baixarAtualizacao,
  configurarAtualizacao,
  esperarVersaoNova,
  instalarAtualizacao,
  procurarAtualizacao,
  useAtualizacao,
  type EstadoAtualizacao,
} from '../lib/atualizacao';

const SITE = 'https://dracon-46.github.io/nicx/';

function base(versao: string): string {
  return (versao.match(/^\d+\.\d+\.\d+/) ?? [versao])[0];
}

function compara(a: string, b: string): number {
  const pa = base(a).split('.').map(Number);
  const pb = base(b).split('.').map(Number);
  for (let i = 0; i < 3; i++) if ((pa[i] ?? 0) !== (pb[i] ?? 0)) return (pa[i] ?? 0) - (pb[i] ?? 0);
  return 0;
}

const botao = 'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-default';
const primario = { background: 'var(--color-accent)', color: 'var(--color-on-accent, white)', border: '1px solid var(--color-accent)' };
const secundario = { background: 'var(--color-bg-secondary)', color: 'var(--color-text)', border: '1px solid var(--color-border)' };

export function UpdatesPage() {
  const { t, i18n } = useTranslation();
  const estado = useAtualizacao((s) => s.estado);
  const definir = useAtualizacao((s) => s.definir);
  const [ocupado, setOcupado] = useState<'procurar' | 'atualizar' | null>(null);
  const [erro, setErro] = useState('');
  const [instalando, setInstalando] = useState<'esperando' | 'demorou' | null>(null);
  const querInstalar = useRef(false);

  const data = (iso: string | null | undefined, comHora = false) => {
    if (!iso) return '';
    const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
    return comHora ? d.toLocaleString(i18n.language) : d.toLocaleDateString(i18n.language);
  };

  useEffect(() => {
    void atualizarEstado();
  }, []);

  const instalar = useCallback(async (atual: EstadoAtualizacao) => {
    try {
      const { versao } = await instalarAtualizacao();
      setInstalando('esperando');
      esperarVersaoNova(
        versao,
        () => window.location.reload(),
        () => setInstalando('demorou'),
      );
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
      setOcupado(null);
      definir(atual);
    }
  }, [definir]);

  // Enquanto baixa: acompanha o progresso; ao terminar, instala.
  useEffect(() => {
    if (!estado) return;
    if (querInstalar.current && estado.pronto_para_instalar && !estado.baixando) {
      querInstalar.current = false;
      void instalar(estado);
      return;
    }
    if (!estado.baixando) return;
    const id = setTimeout(async () => {
      const novo = await atualizarEstado();
      if (novo && !novo.baixando && !novo.pronto_para_instalar) {
        querInstalar.current = false;
        setOcupado(null);
        if (novo.erro_download) setErro(novo.erro_download);
      }
    }, 800);
    return () => clearTimeout(id);
  }, [estado, instalar]);

  const procurar = async () => {
    setOcupado('procurar');
    setErro('');
    try {
      definir(await procurarAtualizacao());
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setOcupado(null);
    }
  };

  const atualizar = async () => {
    if (!estado) return;
    setOcupado('atualizar');
    setErro('');
    querInstalar.current = true;
    try {
      if (estado.pronto_para_instalar) {
        querInstalar.current = false;
        await instalar(estado);
        return;
      }
      definir(await baixarAtualizacao());
    } catch (e) {
      querInstalar.current = false;
      setOcupado(null);
      setErro(e instanceof Error ? e.message : String(e));
    }
  };

  const alternarAutomatica = async () => {
    if (!estado) return;
    try {
      definir(await configurarAtualizacao(!estado.automatica));
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    }
  };

  if (instalando) {
    return (
      <div className="flex-1 flex items-center justify-center p-6" role="status" data-testid="updates-installing">
        <div className="max-w-md text-center space-y-3">
          {instalando === 'esperando' ? (
            <Loader2 size={28} className="animate-spin mx-auto" style={{ color: 'var(--color-accent)' }} />
          ) : (
            <ArrowUpCircle size={28} className="mx-auto" style={{ color: 'var(--color-warning)' }} />
          )}
          <h1 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
            {t(instalando === 'esperando' ? 'atualizacoes.instalandoTitulo' : 'atualizacoes.demorouTitulo')}
          </h1>
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
            {t(instalando === 'esperando' ? 'atualizacoes.instalandoTexto' : 'atualizacoes.demorouTexto')}
          </p>
        </div>
      </div>
    );
  }

  const nova = estado?.ha_nova ? estado.ultima : null;
  const progresso = Math.round((estado?.progresso ?? 0) * 100);

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
        <header>
          <h1 className="text-xl font-semibold flex items-center gap-2" style={{ color: 'var(--color-text)' }}>
            <ArrowUpCircle size={20} style={{ color: 'var(--color-accent)' }} /> {t('atualizacoes.titulo')}
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--color-text-secondary)' }}>
            {t('atualizacoes.intro')}
          </p>
        </header>

        <section
          className="rounded-xl p-4 space-y-3"
          style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
          data-testid="updates-status"
        >
          {!estado ? (
            <Loader2 size={16} className="animate-spin" style={{ color: 'var(--color-text-tertiary)' }} />
          ) : (
            <>
              <p className="text-sm" style={{ color: 'var(--color-text)' }}>
                {t('atualizacoes.voceTem', { versao: base(estado.versao_atual) })}
              </p>
              {nova ? (
                <p className="text-sm font-medium flex items-center gap-1.5" style={{ color: 'var(--color-accent)' }} data-testid="updates-new">
                  <Sparkles size={14} /> {t('atualizacoes.disponivel', { versao: nova.versao, data: data(nova.publicado_em) })}
                </p>
              ) : estado.ultima && !estado.erro ? (
                <p className="text-sm flex items-center gap-1.5" style={{ color: 'var(--color-success)' }}>
                  <CheckCircle2 size={14} /> {t('atualizacoes.emDia')}
                </p>
              ) : null}
              {estado.erro && (
                <p className="text-xs" style={{ color: 'var(--color-warning)' }}>
                  {t('atualizacoes.naoProcurou', { motivo: estado.erro })}
                </p>
              )}
              {estado.verificado_em && (
                <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                  {t('atualizacoes.procuradoEm', { quando: data(estado.verificado_em, true) })}
                </p>
              )}

              <div className="flex flex-wrap items-center gap-2 pt-1">
                <button type="button" onClick={() => void procurar()} disabled={ocupado !== null} className={botao} style={secundario} data-testid="updates-check">
                  {ocupado === 'procurar' ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />} {t('atualizacoes.procurar')}
                </button>
                {nova && estado.pode_instalar && (
                  <button type="button" onClick={() => void atualizar()} disabled={ocupado !== null} className={botao} style={primario} data-testid="updates-install">
                    {ocupado === 'atualizar' ? <Loader2 size={14} className="animate-spin" /> : <ArrowUpCircle size={14} />}{' '}
                    {t('atualizacoes.atualizarPara', { versao: nova.versao })}
                  </button>
                )}
              </div>

              {nova && estado.pode_instalar && (
                <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                  {t('atualizacoes.aviso', { mb: nova.tamanho ? Math.round(nova.tamanho / 1e6) : '?' })}
                </p>
              )}
              {estado.baixando && (
                <div className="space-y-1" role="status" data-testid="updates-progress">
                  <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--color-bg-tertiary)' }}>
                    <div className="h-full transition-all" style={{ width: `${progresso}%`, background: 'var(--color-accent)' }} />
                  </div>
                  <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                    {t('atualizacoes.baixando', { progresso })}
                  </p>
                </div>
              )}
              {nova && estado.instalacao === 'git' && (
                <p className="text-sm flex items-center gap-1.5" style={{ color: 'var(--color-text-secondary)' }}>
                  <Terminal size={14} /> {t('atualizacoes.peloTerminal')} <code className="font-mono">{estado.comando_git}</code>
                </p>
              )}
              {nova && estado.instalacao === 'outro' && (
                <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                  {t('atualizacoes.peloSite')}{' '}
                  <a href={SITE} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--color-accent)' }}>
                    {SITE.replace('https://', '')}
                  </a>
                </p>
              )}
              {erro && (
                <p className="text-sm" role="alert" style={{ color: 'var(--color-error)' }}>
                  {erro}
                </p>
              )}

              <label className="flex items-center justify-between gap-3 pt-2 text-sm" style={{ color: 'var(--color-text)', borderTop: '1px solid var(--color-border)' }}>
                <span className="pt-2">
                  {t('atualizacoes.automatica')}
                  <span className="block text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                    {t('atualizacoes.automaticaDescricao')}
                  </span>
                </span>
                <button
                  type="button"
                  role="switch"
                  aria-checked={estado.automatica}
                  aria-label={t('atualizacoes.automatica')}
                  onClick={() => void alternarAutomatica()}
                  className="relative w-11 h-6 rounded-full transition-colors cursor-pointer shrink-0 mt-2"
                  style={{ background: estado.automatica ? 'var(--color-accent)' : 'var(--color-bg-tertiary)' }}
                  data-testid="updates-auto"
                >
                  <span
                    className="absolute top-0.5 left-0.5 w-5 h-5 rounded-full transition-transform bg-white"
                    style={{ transform: estado.automatica ? 'translateX(20px)' : 'translateX(0)', boxShadow: '0 1px 3px rgba(0,0,0,0.2)' }}
                  />
                </button>
              </label>
            </>
          )}
        </section>

        <section className="space-y-4" data-testid="updates-news">
          <h2 className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
            {t('atualizacoes.novidades')}
          </h2>
          {(estado?.novidades ?? []).map((n) => {
            const relacao = estado ? compara(n.versao, estado.versao_atual) : -1;
            return (
              <article key={n.versao} className="rounded-xl p-4" style={{ border: '1px solid var(--color-border)' }}>
                <div className="flex flex-wrap items-baseline gap-2">
                  <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                    {n.versao} · {n.titulo}
                  </h3>
                  <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>{data(n.data)}</span>
                  {relacao === 0 && (
                    <span className="text-[11px] px-1.5 py-0.5 rounded" style={{ background: 'var(--color-accent-subtle)', color: 'var(--color-accent)' }}>
                      {t('atualizacoes.instalada')}
                    </span>
                  )}
                  {relacao > 0 && (
                    <span className="text-[11px] px-1.5 py-0.5 rounded" style={{ background: 'var(--color-accent)', color: 'white' }}>
                      {t('atualizacoes.nova')}
                    </span>
                  )}
                </div>
                <ul className="mt-2 space-y-1 text-sm list-disc pl-5" style={{ color: 'var(--color-text-secondary)' }}>
                  {n.itens.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </article>
            );
          })}
        </section>
      </div>
    </div>
  );
}
