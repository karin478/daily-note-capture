// A book's note as it opens: the section you talk into, today's date in it, the cursor under that date.
// Only the editor gets these changes; they reach the file with the first thing you type.

const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// Where the first line matching `re` starts at or after `from`, or -1.
function findLine(text, re, from) {
  const g = new RegExp(re.source, 'gm');
  g.lastIndex = from;
  const m = g.exec(text);
  return m ? m.index : -1;
}

const lineEnd = (text, at) => {
  const nl = text.indexOf('\n', at);
  return nl < 0 ? text.length : nl + 1;
};

// Empty frontmatter fields the book list knows get filled; `updated` follows today.
function frontmatter(head, { author, cover, doubanId }, day) {
  const fill = (name, value) => {
    if (value) head = head.replace(new RegExp(`^${name}:[ \\t]*(null|~)?[ \\t]*$`, 'm'), `${name}: ${value}`);
  };
  fill('author', author);
  fill('cover', cover);
  fill('douban_id', doubanId && `"${doubanId}"`);
  return head.replace(/^updated:.*$/m, `updated: ${day}`);
}

// cursor: where to put it, or -1 to go back to where you left it (same day, and the panel remembers).
export function prepareBookNote(body, { section, day, fill = {}, remembered }) {
  let text = body;
  const fm = /^---\n(?:[\s\S]*?\n)?---[ \t]*(?:\n|$)/.exec(text);
  const head = fm ? frontmatter(fm[0], fill, day) : '';
  if (fm) text = head + text.slice(fm[0].length);
  const start = head.length;

  const heading = new RegExp(`^## ${escape(section)}[ \\t]*$`);
  let sectionAt = findLine(text, heading, start);
  if (sectionAt < 0) {
    const next = findLine(text, /^## /, start);
    if (next >= 0) {
      text = text.slice(0, next) + `## ${section}\n\n` + text.slice(next);
    } else {
      const kept = text.replace(/\s+$/, '');
      text = kept + (kept ? '\n\n' : '') + `## ${section}\n`;
    }
    sectionAt = findLine(text, heading, start);
  }
  const inside = lineEnd(text, sectionAt);
  const next = findLine(text, /^#{1,2} /, inside);
  const sectionEnd = next < 0 ? text.length : next;

  const todayAt = findLine(text.slice(0, sectionEnd), new RegExp(`^### ${escape(day)}[ \\t]*$`), inside);
  if (todayAt < 0) {
    const kept = text.slice(sectionAt, sectionEnd).replace(/\s+$/, '');
    const added = `\n\n### ${day}\n`;
    text = text.slice(0, sectionAt) + kept + added + (next < 0 ? '' : '\n\n') + text.slice(sectionEnd);
    return { body: text, cursor: sectionAt + kept.length + added.length, newDay: true };
  }
  if (remembered) return { body: text, cursor: -1, newDay: false };
  const words = lineEnd(text, todayAt);
  const after = findLine(text.slice(0, sectionEnd), /^#{1,3} /, words);
  const said = text.slice(words, after < 0 ? sectionEnd : after).replace(/\s+$/, '');
  return { body: text, cursor: words + said.length, newDay: false };
}
