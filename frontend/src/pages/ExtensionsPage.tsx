import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { BookOpen, Package, Plug, Puzzle } from 'lucide-react';
import { PacksTab } from '../components/Extensions/PacksTab';
import { McpTab } from '../components/Extensions/McpTab';
import { SkillsTab } from '../components/Extensions/SkillsTab';

const TABS = [
  { id: 'packs', icon: Package },
  { id: 'mcp', icon: Plug },
  { id: 'skills', icon: BookOpen },
] as const;

type Tab = (typeof TABS)[number]['id'];

export function ExtensionsPage() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>('packs');

  return (
    <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-10">
      <div className="max-w-3xl mx-auto">
        <header className="mb-5">
          <h1 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--color-text)' }}>
            <Puzzle size={18} /> {t('extensoes.title')}
          </h1>
          <p className="text-sm mt-2 max-w-2xl" style={{ color: 'var(--color-text-secondary)' }}>
            {t('extensoes.subtitle')}
          </p>
        </header>
        <div role="tablist" className="flex flex-wrap gap-1 mb-5" style={{ borderBottom: '1px solid var(--color-border)' }}>
          {TABS.map(({ id, icon: Icon }) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              onClick={() => setTab(id)}
              className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium cursor-pointer -mb-px"
              style={{
                color: tab === id ? 'var(--color-accent)' : 'var(--color-text-secondary)',
                borderBottom: `2px solid ${tab === id ? 'var(--color-accent)' : 'transparent'}`,
                background: 'transparent',
              }}
              data-testid={`ext-tab-${id}`}
            >
              <Icon size={13} /> {t(`extensoes.tabs.${id}`)}
            </button>
          ))}
        </div>
        {tab === 'packs' && <PacksTab />}
        {tab === 'mcp' && <McpTab />}
        {tab === 'skills' && <SkillsTab />}
      </div>
    </div>
  );
}
