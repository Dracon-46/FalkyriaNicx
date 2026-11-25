import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import {
  Bell,
  Brain,
  Briefcase,
  CalendarDays,
  FolderKanban,
  History,
  Loader2,
  MessageSquare,
  Search,
  StickyNote,
} from 'lucide-react';
import { useAppStore } from '../lib/store';
import { buscarConversas, buscarNoServidor, palavras, type SearchHit, type SearchSource } from '../lib/busca';

const ORDEM: SearchSource[] = ['conversa', 'projeto', 'trabalho', 'nota', 'compromisso', 'lembrete', 'memoria', 'historico'];

const ICONES: Record<SearchSource, typeof Search> = {
  conversa: MessageSquare,
  projeto: FolderKanban,
  trabalho: Briefcase,
  nota: StickyNote,
  compromisso: CalendarDays,
  lembrete: Bell,
  memoria: Brain,
  historico: History,
};

const card = {
  background: 'var(--color-bg-secondary)',
  border: '1px solid var(--color-border)',
} as const;

function quando(iso: string, lang: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString(lang, { day: 'numeric', month: 'short', year: 'numeric' });
}

/** Destaca as palavras buscadas no texto (sem acento, sem maiúscula). */
function Destaque({ texto, termos }: { texto: string; termos: string[] }) {
  if (!termos.length || !texto) return <>{texto}</>;
  const norm = texto.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase();
  // NFKD pode mudar o tamanho; só destaca quando as posições batem.
  if (norm.length !== texto.length) return <>{texto}</>;
  const marcas: [number, number][] = [];
  for (const termo of termos) {
    for (let i = norm.indexOf(termo); i >= 0; i = norm.indexOf(termo, i + termo.length)) marcas.push([i, i + termo.length]);
  }
  marcas.sort((a, b) => a[0] - b[0]);
  const partes: React.ReactNode[] = [];
  let pos = 0;
  for (const [ini, fim] of marcas) {
    if (ini < pos) continue;
    if (ini > pos) partes.push(texto.slice(pos, ini));
    partes.push(
      <mark key={ini} style={{ background: 'color-mix(in srgb, var(--color-accent) 25%, transparent)', color: 'inherit', borderRadius: 2 }}>
        {texto.slice(ini, fim)}
      </mark>,
    );
    pos = fim;
  }
  partes.push(texto.slice(pos));
  return <>{partes}</>;
}

export function SearchPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const conversations = useAppStore((s) => s.conversations);
  const selectConversation = useAppStore((s) => s.selectConversation);
  const [busca, setBusca] = useState('');
  const [servidor, setServidor] = useState<SearchHit[]>([]);
  const [falharam, setFalharam] = useState<string[]>([]);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => inputRef.current?.focus(), []);

  const termos = useMemo(() => palavras(busca), [busca]);
  const locais = useMemo(() => buscarConversas(conversations, busca), [conversations, busca]);

  useEffect(() => {
    if (!termos.length) {
      setServidor([]);
      setFalharam([]);
      setErro('');
      return;
    }
    const ctrl = new AbortController();
    const timer = setTimeout(() => {
      setCarregando(true);
      buscarNoServidor(busca, ctrl.signal)
        .then((r) => {
          setServidor(r.resultados);
          setFalharam(r.falharam);
          setErro('');
        })
        .catch((e) => {
          if (!ctrl.signal.aborted) setErro(e instanceof Error && e.message === '404' ? t('busca.restartServer') : t('busca.failed'));
        })
        .finally(() => {
          if (!ctrl.signal.aborted) setCarregando(false);
        });
    }, 300);
    return () => {
      ctrl.abort();
      clearTimeout(timer);
    };
  }, [busca, termos.length, t]);

  const grupos = useMemo(() => {
    const todos = [...locais, ...servidor];
    return ORDEM.map((fonte) => ({ fonte, itens: todos.filter((x) => x.fonte === fonte) })).filter((g) => g.itens.length);
  }, [locais, servidor]);
  const total = grupos.reduce((n, g) => n + g.itens.length, 0);

  const abrir = (hit: SearchHit) => {
    if (hit.fonte === 'conversa') {
      selectConversation(hit.ref);
      navigate('/');
    } else if (hit.fonte === 'projeto') {
      navigate('/projetos', { state: { projeto: hit.ref } });
    } else if (hit.fonte === 'trabalho') {
      navigate('/trabalho', { state: { tarefa: hit.ref } });
    } else if (hit.link) {
      navigate(hit.link);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-10">
      <div className="max-w-3xl mx-auto">
        <header className="mb-5">
          <h1 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--color-text)' }}>
            <Search size={18} /> {t('busca.title')}
          </h1>
          <p className="text-sm mt-2" style={{ color: 'var(--color-text-secondary)' }}>
            {t('busca.subtitle')}
          </p>
        </header>

        <div className="relative mb-5">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--color-text-tertiary)' }} />
          <input
            ref={inputRef}
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            maxLength={200}
            placeholder={t('busca.placeholder')}
            aria-label={t('busca.title')}
            className="w-full pl-9 pr-9 py-2.5 rounded-xl text-sm"
            style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
            data-testid="search-input"
          />
          {carregando && (
            <Loader2 size={14} className="absolute right-3 top-1/2 -translate-y-1/2 animate-spin" style={{ color: 'var(--color-text-tertiary)' }} />
          )}
        </div>

        {erro && (
          <p className="text-xs mb-3" role="alert" style={{ color: 'var(--color-error)' }}>
            {erro}
          </p>
        )}
        {falharam.length > 0 && (
          <p className="text-xs mb-3" style={{ color: 'var(--color-warning)' }}>
            {t('busca.partial', { sources: falharam.map((f) => t(`busca.sources.${f}`)).join(', ') })}
          </p>
        )}

        {termos.length > 0 && !carregando && total === 0 && !erro && (
          <p className="text-sm" style={{ color: 'var(--color-text-tertiary)' }} data-testid="search-empty">
            {t('busca.empty', { query: busca.trim() })}
          </p>
        )}
        {termos.length === 0 && (
          <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
            {t('busca.hint')}
          </p>
        )}

        <div className="space-y-5">
          {grupos.map(({ fonte, itens }) => {
            const Icone = ICONES[fonte];
            return (
              <section key={fonte} data-testid={`search-group-${fonte}`}>
                <h2 className="text-xs font-semibold uppercase tracking-wider mb-2 flex items-center gap-1.5" style={{ color: 'var(--color-text-secondary)' }}>
                  <Icone size={12} /> {t(`busca.sources.${fonte}`)} ({itens.length})
                </h2>
                <ul className="space-y-1.5">
                  {itens.map((hit) => {
                    const clicavel = hit.fonte === 'conversa' || Boolean(hit.link);
                    const conteudo = (
                      <>
                        <div className="flex items-start justify-between gap-2">
                          <span className="text-sm break-words min-w-0" style={{ color: 'var(--color-text)' }}>
                            <Destaque texto={hit.titulo} termos={termos} />
                          </span>
                          <span className="text-[11px] shrink-0" style={{ color: 'var(--color-text-tertiary)' }}>
                            {quando(hit.quando, i18n.language)}
                          </span>
                        </div>
                        {hit.trecho && (
                          <p className="text-xs mt-1 break-words" style={{ color: 'var(--color-text-secondary)' }}>
                            <Destaque texto={hit.trecho} termos={termos} />
                          </p>
                        )}
                      </>
                    );
                    return (
                      <li key={`${hit.fonte}-${hit.ref}`}>
                        {clicavel ? (
                          <button type="button" onClick={() => abrir(hit)} className="w-full text-start rounded-lg px-3 py-2 cursor-pointer" style={card} data-testid={`search-hit-${hit.fonte}`}>
                            {conteudo}
                          </button>
                        ) : (
                          <div className="rounded-lg px-3 py-2" style={card} data-testid={`search-hit-${hit.fonte}`}>
                            {conteudo}
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </section>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default SearchPage;
