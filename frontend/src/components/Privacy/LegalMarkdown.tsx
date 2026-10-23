import type { ComponentProps } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

type WithNode<T extends 'a' | 'ul' | 'ol'> = ComponentProps<T> & { node?: unknown };

function ExternalLink({ href, children, node: _node, ...rest }: WithNode<'a'>) {
  const external = !!href && /^(https?:|mailto:)/i.test(href);
  return (
    <a
      {...rest}
      href={href}
      {...(external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
    >
      {children}
    </a>
  );
}

// Tailwind's reset removes list markers; legal texts need them back.
const components = {
  a: ExternalLink,
  ul: ({ node: _node, ...props }: WithNode<'ul'>) => <ul {...props} className="list-disc" />,
  ol: ({ node: _node, ...props }: WithNode<'ol'>) => <ol {...props} className="list-decimal" />,
};

/** Legal and consent texts, rendered like Nicx's chat replies. */
export function LegalMarkdown({ children }: { children: string }) {
  return (
    <div className="prose max-w-none" style={{ color: 'var(--color-text)' }}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
