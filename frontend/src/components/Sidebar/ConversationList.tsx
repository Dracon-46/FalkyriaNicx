import { Trash2 } from 'lucide-react';
import { useNavigate } from 'react-router';
import { useAppStore } from '../../lib/store';
import { useTranslation } from 'react-i18next';
import i18n from '../../i18n';

interface Props {
  searchQuery: string;
}

function formatRelativeTime(timestamp: number): string {
  const diff = Date.now() - timestamp;
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return i18n.t('nav.chats.justNow');
  const rtf = new Intl.RelativeTimeFormat(i18n.language, { numeric: 'auto', style: 'short' });
  if (minutes < 60) return rtf.format(-minutes, 'minute');
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return rtf.format(-hours, 'hour');
  const days = Math.floor(hours / 24);
  if (days < 7) return rtf.format(-days, 'day');
  return new Date(timestamp).toLocaleDateString(i18n.language);
}

/** Default titles are stored in English (the store compares them); show them translated. */
function displayTitle(title: string): string {
  if (title === 'New chat') return i18n.t('nav.newChat');
  if (title === 'Overlay chat') return i18n.t('nav.chats.overlay');
  return title;
}

export function ConversationList({ searchQuery }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const conversations = useAppStore((s) => s.conversations);
  const activeId = useAppStore((s) => s.activeId);
  const streamingConversationId = useAppStore((s) =>
    s.streamState.isStreaming ? s.streamState.conversationId : null,
  );
  const selectConversation = useAppStore((s) => s.selectConversation);
  const deleteConversation = useAppStore((s) => s.deleteConversation);

  const filtered = searchQuery
    ? conversations.filter((c) =>
        displayTitle(c.title).toLowerCase().includes(searchQuery.toLowerCase()),
      )
    : conversations;

  if (filtered.length === 0) {
    return (
      <div className="px-3 py-8 text-center text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
        {searchQuery ? t('nav.chats.noMatches') : t('nav.chats.empty')}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-0.5 py-1">
      {filtered.map((conv) => {
        const isActive = conv.id === activeId;
        const isStreaming = conv.id === streamingConversationId;
        return (
          <div
            key={conv.id}
            className="group flex items-center rounded-lg cursor-pointer transition-colors"
            style={{
              background: isActive ? 'var(--color-bg-tertiary)' : 'transparent',
            }}
            onMouseEnter={(e) => {
              if (!isActive) e.currentTarget.style.background = 'var(--color-bg-secondary)';
            }}
            onMouseLeave={(e) => {
              if (!isActive) e.currentTarget.style.background = 'transparent';
            }}
          >
            <button
              onClick={() => {
                selectConversation(conv.id);
                navigate('/');
              }}
              className="flex-1 text-left px-3 py-2 min-w-0 cursor-pointer"
            >
              <div
                className="text-sm truncate"
                style={{
                  color: isActive ? 'var(--color-text)' : 'var(--color-text-secondary)',
                  fontWeight: isActive ? 500 : 400,
                }}
              >
                {displayTitle(conv.title)}
              </div>
              <div className="text-[11px] mt-0.5" style={{ color: 'var(--color-text-tertiary)' }}>
                {formatRelativeTime(conv.updatedAt)}
              </div>
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                deleteConversation(conv.id);
              }}
              disabled={isStreaming}
              className="p-1.5 mr-1 rounded opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer disabled:cursor-not-allowed disabled:opacity-30"
              style={{ color: 'var(--color-text-tertiary)' }}
              onMouseEnter={(e) => {
                if (!isStreaming) e.currentTarget.style.color = 'var(--color-error)';
              }}
              onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--color-text-tertiary)')}
              title={
                isStreaming
                  ? t('nav.chats.stopBeforeDelete')
                  : t('nav.chats.delete')
              }
            >
              <Trash2 size={14} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
