import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { CheckCircle2, Code2, Loader2 } from 'lucide-react';
import { estadoVSCode, instalarVSCode, type EstadoVSCode } from '../../lib/vscode';

/** Ligar o Nicx ao VS Code: instala a extensão com um clique. */
export function VSCodeSettings() {
  const { t } = useTranslation();
  const [estado, setEstado] = useState<EstadoVSCode | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState('');
  const [aviso, setAviso] = useState('');

  useEffect(() => {
    let vivo = true;
    estadoVSCode()
      .then((e) => vivo && setEstado(e))
      .catch(() => vivo && setEstado({ vscode: false, pacote: false, instalada: null }));
    return () => {
      vivo = false;
    };
  }, []);

  const instalar = async () => {
    setOcupado(true);
    setErro('');
    setAviso('');
    try {
      const novo = await instalarVSCode();
      setEstado(novo);
      setAviso(t('settings.vscode.pronto'));
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setOcupado(false);
    }
  };

  const botao = 'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-default';

  return (
    <div className="space-y-2" data-testid="vscode-settings">
      <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
        {t('settings.vscode.intro')}
      </p>
      {!estado ? (
        <Loader2 size={14} className="animate-spin" style={{ color: 'var(--color-text-tertiary)' }} />
      ) : !estado.vscode ? (
        <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }} data-testid="vscode-sem">
          {t('settings.vscode.semVSCode')}
        </p>
      ) : !estado.pacote ? (
        <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
          {t('settings.vscode.semPacote')}
        </p>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => void instalar()}
            disabled={ocupado}
            className={botao}
            style={{ background: 'var(--color-accent)', color: 'var(--color-on-accent, white)' }}
            data-testid="vscode-instalar"
          >
            {ocupado ? <Loader2 size={12} className="animate-spin" /> : <Code2 size={12} />}
            {estado.instalada ? t('settings.vscode.atualizar') : t('settings.vscode.conectar')}
          </button>
          {estado.instalada && (
            <span className="text-xs inline-flex items-center gap-1" style={{ color: 'var(--color-success)' }} data-testid="vscode-instalada">
              <CheckCircle2 size={12} /> {t('settings.vscode.instalada', { versao: estado.instalada })}
            </span>
          )}
        </div>
      )}
      {aviso && (
        <p className="text-xs" role="status" style={{ color: 'var(--color-success)' }}>
          {aviso}
        </p>
      )}
      {erro && (
        <p className="text-xs" role="alert" style={{ color: 'var(--color-error)' }}>
          {erro}
        </p>
      )}
    </div>
  );
}
