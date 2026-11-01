/** Keep UUID-backed mentions stable while the textarea displays friendly names. */
const pattern = /@\[([^\]\n]{1,255})\]\(([0-9a-fA-F-]{36})\)/g;
export interface MentionToken { start: number; end: number; raw: string; label: string; id: string }
export function mentionText(raw: string): { text: string; tokens: MentionToken[] } {
  let text = "", end = 0;
  const tokens: MentionToken[] = [];
  for (const match of raw.matchAll(pattern)) {
    text += raw.slice(end, match.index);
    const label = "@" + match[1];
    tokens.push({ start: text.length, end: text.length + label.length, raw: match[0], label, id: match[2] });
    text += label; end = match.index! + match[0].length;
  }
  return { text: text + raw.slice(end), tokens };
}
function encode(text: string, tokens: MentionToken[]) {
  let raw = "", position = 0;
  for (const token of tokens.sort((a,b) => a.start-b.start)) { raw += text.slice(position, token.start) + token.raw; position = token.end; }
  return raw + text.slice(position);
}
export function editMentionText(raw: string, next: string): string {
  const { text, tokens } = mentionText(raw);
  let prefix = 0, suffix = 0;
  while (prefix < text.length && prefix < next.length && text[prefix] === next[prefix]) prefix++;
  while (suffix < text.length-prefix && suffix < next.length-prefix && text[text.length-1-suffix] === next[next.length-1-suffix]) suffix++;
  const end = text.length-suffix, shift = next.length-text.length;
  const keep = tokens.filter(t => t.end <= prefix || t.start >= end).map(t => t.start >= end ? { ...t, start: t.start+shift, end: t.end+shift } : t);
  return encode(next, keep);
}
export function insertMention(raw: string, start: number, end: number, member: { user_id: string; full_name: string }): { raw: string; caret: number } {
  const before = mentionText(raw).text;
  const name = member.full_name.replace(/[\]\n]/g, " ");
  const label = "@" + name;
  const next = before.slice(0,start) + label + " " + before.slice(end);
  const updated = mentionText(editMentionText(raw,next));
  const tokens = updated.tokens.filter(t => t.end <= start || t.start >= start+label.length);
  tokens.push({ start, end:start+label.length, label, raw:`@[${name}](${member.user_id})`, id:member.user_id });
  return { raw:encode(next,tokens), caret:start+label.length+1 };
}
