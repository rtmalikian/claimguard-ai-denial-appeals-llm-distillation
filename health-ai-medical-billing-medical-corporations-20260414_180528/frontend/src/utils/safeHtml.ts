import DOMPurify from 'dompurify';

const DISPLAY_HTML_CONFIG = {
  ALLOWED_TAGS: ['br'],
  ALLOWED_ATTR: [],
};

const escapeDisplayText = (value: string) =>
  value.replace(/[&<>"']/g, (char) => {
    switch (char) {
      case '&':
        return '&amp;';
      case '<':
        return '&lt;';
      case '>':
        return '&gt;';
      case '"':
        return '&quot;';
      case "'":
        return '&#39;';
      default:
        return char;
    }
  });

export const sanitizeToDisplayHtml = (value: unknown, emptyText = '') => {
  const rawValue = value === null || value === undefined || value === '' ? emptyText : String(value);
  const escapedValue = escapeDisplayText(rawValue).replace(/\r\n|\r|\n/g, '<br>');
  return DOMPurify.sanitize(escapedValue, DISPLAY_HTML_CONFIG);
};
