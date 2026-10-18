// Obsidian-style suggestions: `[[` for notes (and `![[` for attachments too), `#` for tags.

export function wikilinkCompletions(context, notes, files) {
  const m = context.matchBefore(/!?\[\[[^\]\n]*$/);
  if (!m) return null;
  const embed = m.text.startsWith('!');
  const closed = context.state.sliceDoc(context.pos, context.pos + 2) === ']]';
  const option = (label, detail) => ({ label, detail, apply: closed ? label : label + ']]', type: 'text' });
  const options = notes.map((n) => option(n.name, n.folder || undefined));
  if (embed) for (const f of files) if (!f.endsWith('.md')) options.push(option(f));
  return { from: m.from + (embed ? 3 : 2), options, validFor: /^[^\]\n|#]*$/ };
}

export function tagCompletions(context, tags) {
  const m = context.matchBefore(/(?:^|\s)#[^\s#]*$/);
  if (!m) return null;
  const hash = m.from + m.text.indexOf('#');
  // A bare "#" at the start of a line is a heading being typed.
  const line = context.state.doc.lineAt(context.pos);
  if (hash === line.from && context.pos === hash + 1 && !context.explicit) return null;
  return { from: hash + 1, options: tags.map((label) => ({ label, type: 'keyword' })), validFor: /^[^\s#]*$/ };
}
