import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { ativarAssistente, listarAssistentes, type Assistant } from '../../lib/assistentes';

/**
 * Quem responde no chat: o Nicx ou um dos assistentes do usuário. Some quando
 * não há assistentes. `refreshKey` muda ao fim de cada resposta, porque o
 * usuário também troca falando ("fala com o assistente X", "volta pro Nicx").
 */
export function AssistantPicker({ refreshKey }: { refreshKey: number }) {
  const { t, i18n } = useTranslation();
  const [assistants, setAssistants] = useState<Assistant[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await listarAssistentes(i18n.language);
      setAssistants(data.assistentes);
      setActive(data.ativo);
      setFailed(false);
    } catch {
      setAssistants([]); // servidor antigo sem a rota: o seletor some
    }
  }, [i18n.language]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  if (assistants.length === 0) return null;

  const change = async (value: string) => {
    const id = value || null;
    const previous = active;
    setActive(id);
    try {
      setActive(await ativarAssistente(id));
      setFailed(false);
    } catch {
      setActive(previous);
      setFailed(true);
      // Só a borda vermelha passava despercebida.
      toast.error(t('assistentes.activateFailed'));
    }
  };

  return (
    <label className="flex items-center gap-1.5 text-xs min-w-0" style={{ color: 'var(--color-text-secondary)' }}>
      <Sparkles size={13} style={{ color: active ? 'var(--color-accent)' : 'var(--color-text-tertiary)', flexShrink: 0 }} />
      <span className="sr-only">{t('assistentes.picker.label')}</span>
      <select
        value={active ?? ''}
        onChange={(e) => void change(e.target.value)}
        className="px-2 py-1 rounded-md text-xs min-w-0 max-w-[14rem] cursor-pointer"
        style={{
          background: 'var(--color-bg-secondary)',
          border: `1px solid ${failed ? 'var(--color-error)' : active ? 'var(--color-accent)' : 'var(--color-border)'}`,
          color: 'var(--color-text)',
        }}
        title={failed ? t('assistentes.activateFailed') : t('assistentes.picker.label')}
        data-testid="assistant-picker"
      >
        <option value="">{t('assistentes.picker.nicx')}</option>
        {assistants.map((a) => (
          <option key={a.id} value={a.id}>
            {a.nome}
          </option>
        ))}
      </select>
    </label>
  );
}
