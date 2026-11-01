// Find a quoted passage in its source record, the same way the citation check does: ignoring case
// and runs of whitespace. Returns the record split around the passage, or null when it is absent.
export function locate(text: string, quote: string): [string, string, string] | null {
  const words = quote.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return null;
  const escaped = words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const match = new RegExp(escaped.join("\\s+"), "i").exec(text);
  if (!match) return null;
  const start = match.index;
  const end = start + match[0].length;
  return [text.slice(0, start), text.slice(start, end), text.slice(end)];
}
