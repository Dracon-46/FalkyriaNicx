/**
 * Split a leading Markdown heading off a document so it can label the
 * dialog that shows it ("# Política..." → title + the rest).
 */
export function splitTitle(markdown: string): { title: string; body: string } {
  const match = /^\s*#{1,3}\s+(.+?)\s*#*\s*(?:\r?\n|$)/.exec(markdown);
  if (!match) return { title: '', body: markdown };
  return { title: match[1].trim(), body: markdown.slice(match[0].length).trimStart() };
}
