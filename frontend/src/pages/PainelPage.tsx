import { ArrowUpRight, ShieldCheck } from 'lucide-react';
import { NicxMascot } from '../components/Mascot/NicxMascot';

/** Endereço do Painel Falkyria (repositório próprio, GitHub Pages). */
export const PAINEL_URL = 'https://dracon-46.github.io/nicx-painel/';

/**
 * O Painel Falkyria fica na web, com login de administrador e segundo
 * fator obrigatório. Aqui no app só fica o atalho para ele.
 */
export function PainelPage() {
  return (
    <div className="flex-1 flex items-center justify-center px-4 py-10">
      <div
        className="w-full max-w-md rounded-xl p-6 text-center"
        style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
      >
        <NicxMascot size="md" decorative className="mx-auto" />
        <h1 className="text-lg font-semibold mt-3" style={{ color: 'var(--color-text)' }}>
          Painel Falkyria
        </h1>
        <p className="text-sm mt-2 leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>
          As estatísticas anônimas de uso do Nicx ficam no painel da web, só para administradores da
          Falkyria. A entrada pede senha e o código do app autenticador.
        </p>
        <a
          href={PAINEL_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 mt-5 min-h-9 px-4 py-2 rounded-lg text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-accent)]"
          style={{ background: 'var(--color-accent)', color: 'var(--color-on-accent)' }}
        >
          Abrir o painel <ArrowUpRight size={15} aria-hidden="true" />
        </a>
        <p className="text-xs mt-4 inline-flex items-center gap-1.5" style={{ color: 'var(--color-text-tertiary)' }}>
          <ShieldCheck size={13} aria-hidden="true" /> Acesso restrito e registrado.
        </p>
      </div>
    </div>
  );
}

export default PainelPage;
