import { useMemo } from 'react';
import { sanitizeToDisplayHtml } from '../../utils/safeHtml';

interface SafeHtmlProps {
  value: unknown;
  className?: string;
  emptyText?: string;
  inline?: boolean;
  preformatted?: boolean;
}

export default function SafeHtml({
  value,
  className = '',
  emptyText = '',
  inline = false,
  preformatted = false,
}: SafeHtmlProps) {
  const html = useMemo(() => sanitizeToDisplayHtml(value, emptyText), [emptyText, value]);

  if (inline) {
    return <span className={className} dangerouslySetInnerHTML={{ __html: html }} />;
  }

  if (preformatted) {
    return <pre className={className} dangerouslySetInnerHTML={{ __html: html }} />;
  }

  return <div className={className} dangerouslySetInnerHTML={{ __html: html }} />;
}
