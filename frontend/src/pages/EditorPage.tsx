import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  ChevronDown,
  ChevronRight,
  Code2,
  FileCode2,
  FileUp,
  FlaskConical,
  Folder,
  FolderOpen,
  Lightbulb,
  Loader2,
  MessageSquare,
  Save,
  Sparkles,
  Square,
  Wrench,
} from 'lucide-react';
import { CodeEditor, type EditorApi } from '../components/Editor/CodeEditor';
import { PropostaDiff } from '../components/Editor/PropostaDiff';
import { abrir, ArquivoBinario, ArquivoGrande, escolherPasta, ler, listar, salvar, temPastas, type Aberto, type No } from '../lib/editor/arquivos';
import { ajustarRecuo, COM_PROPOSTA, conversar, extrairCodigo, linguagemDe, MAX_CODIGO, pedido, type Acao } from '../lib/editor/nicx';
import { useAppStore } from '../lib/store';

interface Proposta {
  de: number;
  ate: number;
  original: string;
  novo: string;
  explicacao: string;
}

/** Texto da resposta com os blocos de código destacados (Copiar / Inserir). */
function Resposta({ texto, onInserir }: { texto: string; onInserir: (codigo: string) => void }) {
  const { t } = useTranslation();
  const partes = texto.split(/(```[^\n]*\n[\s\S]*?(?:```|$))/g).filter(Boolean);
  return (
    <div className="space-y-2 text-sm leading-relaxed" style={{ color: 'var(--color-text)' }}>
      {partes.map((parte, i) => {
        const m = parte.match(/^```[^\n]*\n([\s\S]*?)(?:```)?$/);
        if (!m) {
          return (
            <p key={i} className="whitespace-pre-wrap break-words">
              {parte.trim()}
            </p>
          );
        }
        const codigo = m[1].replace(/\n$/, '');
        return (
          <div key={i} className="rounded-lg overflow-hidden" style={{ border: '1px solid var(--color-border)' }}>
            <div className="flex justify-end gap-1 px-2 py-1" style={{ background: 'var(--color-bg-secondary)' }}>
              <button type="button" className="text-[11px] px-2 py-0.5 rounded cursor-pointer" style={{ color: 'var(--color-text-secondary)' }} onClick={() => void navigator.clipboard.writeText(codigo).then(() => toast.success(t('editor.copiado')))}>
                {t('editor.copiar')}
              </button>
              <button type="button" className="text-[11px] px-2 py-0.5 rounded cursor-pointer" style={{ color: 'var(--color-accent)' }} onClick={() => onInserir(codigo)}>
                {t('editor.inserir')}
              </button>
            </div>
            <pre className="p-2 text-[12px] overflow-x-auto font-mono" style={{ background: 'var(--color-bg-tertiary)' }}>
              <code>{codigo}</code>
            </pre>
          </div>
        );
      })}
    </div>
  );
}

function Arvore({
  itens,
  filhos,
  abertas,
  atual,
  nivel,
  onPasta,
  onArquivo,
}: {
  itens: No[];
  filhos: Map<string, No[]>;
  abertas: Set<string>;
  atual: string | null;
  nivel: number;
  onPasta: (no: No) => void;
  onArquivo: (no: No) => void;
}) {
  return (
    <ul>
      {itens.map((no) => {
        const aberta = abertas.has(no.caminho);
        return (
          <li key={no.caminho}>
            <button
              type="button"
              onClick={() => (no.tipo === 'pasta' ? onPasta(no) : onArquivo(no))}
              className="w-full flex items-center gap-1 py-0.5 pr-2 text-left text-xs rounded cursor-pointer truncate"
              style={{
                paddingLeft: 6 + nivel * 12,
                background: atual === no.caminho ? 'var(--color-accent-subtle)' : 'transparent',
                color: atual === no.caminho ? 'var(--color-text)' : 'var(--color-text-secondary)',
              }}
              title={no.caminho}
            >
              {no.tipo === 'pasta' ? (
                <>
                  {aberta ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                  {aberta ? <FolderOpen size={13} /> : <Folder size={13} />}
                </>
              ) : (
                <FileCode2 size={13} className="ml-3" />
              )}
              <span className="truncate">{no.nome}</span>
            </button>
            {no.tipo === 'pasta' && aberta && filhos.get(no.caminho) && (
              <Arvore itens={filhos.get(no.caminho)!} filhos={filhos} abertas={abertas} atual={atual} nivel={nivel + 1} onPasta={onPasta} onArquivo={onArquivo} />
            )}
          </li>
        );
      })}
    </ul>
  );
}

/**
 * Editor de código do app: abre uma pasta (ou um arquivo), edita com cores e
 * pede ao Nicx para explicar, corrigir, melhorar ou testar o trecho
 * selecionado. Correções abrem como diff e só entram com Aplicar.
 */
export function EditorPage() {
  const { t } = useTranslation();
  const selectedModel = useAppStore((s) => s.selectedModel);
  const editor = useRef<EditorApi>(null);
  const entrada = useRef<HTMLInputElement>(null);
  const [pasta, setPasta] = useState<FileSystemDirectoryHandle | null>(null);
  const [raiz, setRaiz] = useState<No[]>([]);
  const [filhos, setFilhos] = useState<Map<string, No[]>>(new Map());
  const [abertas, setAbertas] = useState<Set<string>>(new Set());
  const [aberto, setAberto] = useState<Aberto | null>(null);
  const [texto, setTexto] = useState('');
  const [salvo, setSalvo] = useState('');
  const [pergunta, setPergunta] = useState('');
  const [resposta, setResposta] = useState('');
  const [pensando, setPensando] = useState<Acao | null>(null);
  const [proposta, setProposta] = useState<Proposta | null>(null);
  const parar = useRef<AbortController | null>(null);
  const sujo = aberto !== null && texto !== salvo;

  useEffect(() => {
    if (!sujo) return;
    const aviso = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener('beforeunload', aviso);
    return () => window.removeEventListener('beforeunload', aviso);
  }, [sujo]);

  useEffect(() => () => parar.current?.abort(), []);

  const podeTrocar = () => !sujo || window.confirm(t('editor.descartarMudancas', { nome: aberto?.nome }));

  const erroDeArquivo = (e: unknown, nome: string) => {
    if (e instanceof ArquivoGrande) toast.error(t('editor.erros.grande', { nome }));
    else if (e instanceof ArquivoBinario) toast.error(t('editor.erros.binario', { nome }));
    else toast.error(t('editor.erros.abrir', { nome, detalhe: e instanceof Error ? e.message : String(e) }));
  };

  const mostrar = (a: Aberto) => {
    setAberto(a);
    setTexto(a.texto);
    setSalvo(a.texto);
    setResposta('');
  };

  const abrirPasta = async () => {
    if (!podeTrocar()) return;
    try {
      const p = await escolherPasta();
      if (!p) return;
      setPasta(p);
      setRaiz(await listar(p));
      setFilhos(new Map());
      setAbertas(new Set());
      setAberto(null);
    } catch (e) {
      toast.error(t('editor.erros.pasta', { detalhe: e instanceof Error ? e.message : String(e) }));
    }
  };

  const alternarPasta = async (no: No) => {
    const novas = new Set(abertas);
    if (novas.has(no.caminho)) {
      novas.delete(no.caminho);
      setAbertas(novas);
      return;
    }
    novas.add(no.caminho);
    setAbertas(novas);
    if (!filhos.has(no.caminho)) {
      try {
        const lista = await listar(no.handle as FileSystemDirectoryHandle, no.caminho);
        setFilhos((f) => new Map(f).set(no.caminho, lista));
      } catch (e) {
        toast.error(t('editor.erros.pasta', { detalhe: e instanceof Error ? e.message : String(e) }));
      }
    }
  };

  const abrirArquivo = async (no: No) => {
    if (aberto?.caminho === no.caminho || !podeTrocar()) return;
    try {
      mostrar(await abrir(no));
    } catch (e) {
      erroDeArquivo(e, no.nome);
    }
  };

  const abrirSolto = async (arquivo: File) => {
    if (!podeTrocar()) return;
    try {
      mostrar({ caminho: arquivo.name, nome: arquivo.name, texto: await ler(arquivo) });
    } catch (e) {
      erroDeArquivo(e, arquivo.name);
    }
  };

  const gravar = useCallback(async () => {
    if (!aberto) return;
    const atual = editor.current?.texto() ?? texto;
    try {
      const como = await salvar(aberto, atual);
      setSalvo(atual);
      toast.success(como === 'gravado' ? t('editor.salvo', { nome: aberto.nome }) : t('editor.baixado', { nome: aberto.nome }));
    } catch (e) {
      toast.error(t('editor.erros.salvar', { nome: aberto.nome, detalhe: e instanceof Error ? e.message : String(e) }));
    }
  }, [aberto, texto, t]);

  const pedir = async (acao: Acao) => {
    if (!aberto || !editor.current || pensando) return;
    if (!selectedModel) {
      toast.error(t('editor.semModelo'));
      return;
    }
    const sel = editor.current.selecaoEmLinhas();
    if (sel.texto.length > MAX_CODIGO) {
      toast.error(t('editor.erros.trechoGrande'));
      return;
    }
    if (acao === 'perguntar' && !pergunta.trim()) return;
    const tudo = editor.current.texto();
    const trecho = {
      arquivo: aberto.caminho,
      linguagem: linguagemDe(aberto.nome),
      codigo: sel.texto,
      antes: sel.de > 0 ? tudo.slice(Math.max(0, sel.de - 2000), sel.de) : undefined,
      depois: sel.ate < tudo.length ? tudo.slice(sel.ate, sel.ate + 2000) : undefined,
      linhaInicial: sel.linhaInicial,
    };
    const controle = new AbortController();
    parar.current = controle;
    setPensando(acao);
    setResposta('');
    let acumulado = '';
    try {
      for await (const parte of conversar([{ role: 'user', content: pedido(acao, trecho, pergunta) }], selectedModel, controle.signal)) {
        acumulado += parte;
        setResposta(acumulado);
      }
      if (COM_PROPOSTA.has(acao)) {
        const codigo = extrairCodigo(acumulado);
        if (codigo !== null) {
          let novo = ajustarRecuo(sel.texto, codigo);
          if (sel.texto.endsWith('\n') && !novo.endsWith('\n')) novo += '\n';
          if (novo === sel.texto) toast(t('editor.nadaAMudar'));
          else {
            const explicacao = acumulado.replace(/(```+|~~~+)[^\n]*\n[\s\S]*?\n?\1/, '').trim();
            setProposta({ de: sel.de, ate: sel.ate, original: sel.texto, novo, explicacao });
          }
        }
      }
      if (acao === 'perguntar') setPergunta('');
    } catch (e) {
      if ((e as Error).name !== 'AbortError') setResposta(`⚠ ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      if (parar.current === controle) parar.current = null;
      setPensando(null);
    }
  };

  const aplicar = () => {
    if (!proposta || !editor.current) return;
    // O texto mudou desde o pedido? Só aplica se o trecho ainda é o mesmo.
    const atual = editor.current.texto();
    if (atual.slice(proposta.de, proposta.ate) !== proposta.original) {
      toast.error(t('editor.proposta.mudou'));
      setProposta(null);
      return;
    }
    editor.current.trocar(proposta.de, proposta.ate, proposta.novo);
    setProposta(null);
    toast.success(t('editor.proposta.aplicada'));
  };

  const acoes: Array<{ acao: Acao; icone: typeof Wrench; rotulo: string }> = [
    { acao: 'explicar', icone: Lightbulb, rotulo: t('editor.acoes.explicar') },
    { acao: 'corrigir', icone: Wrench, rotulo: t('editor.acoes.corrigir') },
    { acao: 'melhorar', icone: Sparkles, rotulo: t('editor.acoes.melhorar') },
    { acao: 'testes', icone: FlaskConical, rotulo: t('editor.acoes.testes') },
  ];
  const botao = 'inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-default';
  const secundario = { background: 'var(--color-bg-secondary)', color: 'var(--color-text)', border: '1px solid var(--color-border)' };

  return (
    <div className="flex-1 flex flex-col min-h-0" data-testid="editor-page">
      <div className="flex flex-wrap items-center gap-2 px-3 py-2" style={{ borderBottom: '1px solid var(--color-border)' }}>
        <Code2 size={16} style={{ color: 'var(--color-accent)' }} />
        <h1 className="text-sm font-semibold mr-2" style={{ color: 'var(--color-text)' }}>
          {t('editor.titulo')}
        </h1>
        {temPastas() && (
          <button type="button" onClick={() => void abrirPasta()} className={botao} style={secundario} data-testid="editor-abrir-pasta">
            <FolderOpen size={13} /> {t('editor.abrirPasta')}
          </button>
        )}
        <button type="button" onClick={() => entrada.current?.click()} className={botao} style={secundario} data-testid="editor-abrir-arquivo">
          <FileUp size={13} /> {t('editor.abrirArquivo')}
        </button>
        <input
          ref={entrada}
          type="file"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0];
            e.target.value = '';
            if (f) void abrirSolto(f);
          }}
        />
        {aberto && (
          <>
            <span className="text-xs truncate max-w-[40ch]" style={{ color: 'var(--color-text-secondary)' }} title={aberto.caminho}>
              {aberto.caminho}
              {sujo && <span aria-label={t('editor.naoSalvo')} title={t('editor.naoSalvo')} style={{ color: 'var(--color-accent)' }}> ●</span>}
            </span>
            <button type="button" onClick={() => void gravar()} disabled={!sujo} className={botao} style={{ background: 'var(--color-accent)', color: 'var(--color-on-accent, white)' }} title="Ctrl+S" data-testid="editor-salvar">
              <Save size={13} /> {aberto.handle ? t('editor.salvar') : t('editor.baixar')}
            </button>
          </>
        )}
      </div>

      <div className="flex-1 flex min-h-0">
        {pasta && (
          <nav className="w-56 shrink-0 overflow-y-auto py-2" style={{ borderRight: '1px solid var(--color-border)' }} aria-label={t('editor.arquivos')} data-testid="editor-arvore">
            <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wide truncate" style={{ color: 'var(--color-text-tertiary)' }}>
              {pasta.name}
            </p>
            <Arvore itens={raiz} filhos={filhos} abertas={abertas} atual={aberto?.caminho ?? null} nivel={0} onPasta={(n) => void alternarPasta(n)} onArquivo={(n) => void abrirArquivo(n)} />
          </nav>
        )}

        <div className="flex-1 min-w-0 min-h-0">
          {aberto ? (
            <CodeEditor ref={editor} nome={aberto.caminho} texto={aberto.texto} onChange={setTexto} onSalvar={() => void gravar()} />
          ) : (
            <div className="h-full flex items-center justify-center p-6">
              <div className="max-w-md text-center space-y-2">
                <Code2 size={28} className="mx-auto" style={{ color: 'var(--color-text-tertiary)' }} />
                <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                  {t('editor.vazio')}
                </p>
                {!temPastas() && (
                  <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                    {t('editor.semPastas')}
                  </p>
                )}
              </div>
            </div>
          )}
        </div>

        <aside className="w-80 shrink-0 flex flex-col min-h-0" style={{ borderLeft: '1px solid var(--color-border)' }} aria-label={t('editor.painel')} data-testid="editor-nicx">
          <div className="p-3 space-y-2" style={{ borderBottom: '1px solid var(--color-border)' }}>
            <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
              {t('editor.dica')}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {acoes.map(({ acao, icone: Icone, rotulo }) => (
                <button key={acao} type="button" onClick={() => void pedir(acao)} disabled={!aberto || pensando !== null} className={botao} style={secundario} data-testid={`editor-${acao}`}>
                  {pensando === acao ? <Loader2 size={13} className="animate-spin" /> : <Icone size={13} />} {rotulo}
                </button>
              ))}
            </div>
            <form
              className="flex gap-1.5"
              onSubmit={(e) => {
                e.preventDefault();
                void pedir('perguntar');
              }}
            >
              <input
                value={pergunta}
                onChange={(e) => setPergunta(e.target.value)}
                placeholder={t('editor.perguntar')}
                disabled={!aberto || pensando !== null}
                className="flex-1 min-w-0 px-2 py-1.5 rounded-lg text-xs outline-none"
                style={{ background: 'var(--color-input-bg)', border: '1px solid var(--color-input-border)', color: 'var(--color-text)' }}
                data-testid="editor-pergunta"
              />
              {pensando ? (
                <button type="button" onClick={() => parar.current?.abort()} className={botao} style={{ background: 'var(--color-error)', color: 'white' }} aria-label={t('editor.parar')} title={t('editor.parar')}>
                  <Square size={13} />
                </button>
              ) : (
                <button type="submit" disabled={!aberto || !pergunta.trim()} className={botao} style={secundario} aria-label={t('editor.enviar')} title={t('editor.enviar')}>
                  <MessageSquare size={13} />
                </button>
              )}
            </form>
          </div>
          <div className="flex-1 overflow-y-auto p-3" aria-live="polite" data-testid="editor-resposta">
            {pensando && !resposta && (
              <p className="text-xs italic" style={{ color: 'var(--color-text-tertiary)' }}>
                {t('editor.pensando')}
              </p>
            )}
            {resposta && <Resposta texto={resposta} onInserir={(c) => editor.current?.inserir(c)} />}
          </div>
        </aside>
      </div>

      {proposta && aberto && (
        <PropostaDiff nome={aberto.nome} original={proposta.original} proposta={proposta.novo} explicacao={proposta.explicacao} onAplicar={aplicar} onDescartar={() => setProposta(null)} />
      )}
    </div>
  );
}

export default EditorPage;
