// Obsidian-style live preview, as pure data: which source ranges to hide, restyle or replace.
// The document text is never rewritten; only its display changes, and lines holding the
// cursor show their raw markdown.
import { insertNewlineContinueMarkupCommand, markdown, markdownLanguage } from '@codemirror/lang-markdown';
import { ensureSyntaxTree, syntaxTree } from '@codemirror/language';

// The editor binds its own Enter (newlineInList), so lang-markdown's keymap is left out.
export const markdownExtension = () => markdown({ base: markdownLanguage, addKeymap: false });

const WIKILINK = /\[\[([^\]\n|]+)(\|([^\]\n]+))?\]\]/g;
const HIGHLIGHT = /==([^=\n]+)==/g;
const TIME = /^- (\d{1,2}:\d{2}) /;

function activeLines(state) {
  const lines = new Set();
  for (const r of state.selection.ranges) {
    const a = state.doc.lineAt(r.from).number;
    const b = state.doc.lineAt(r.to).number;
    for (let n = a; n <= b; n++) lines.add(n);
  }
  return lines;
}

export function previewRanges(state) {
  const tree = ensureSyntaxTree(state, state.doc.length, 200) ?? syntaxTree(state);
  const active = activeLines(state);
  const isActive = (pos) => active.has(state.doc.lineAt(pos).number);
  const out = [];
  const code = []; // [from, to] spans where inline regex syntax must not apply
  const linked = []; // [from, to] spans already handled as links

  const lineClass = (from, to, cls) => {
    for (let n = state.doc.lineAt(from).number; n <= state.doc.lineAt(to).number; n++) {
      const line = state.doc.line(n);
      out.push({ from: line.from, to: line.from, type: 'line', cls });
    }
  };
  const cursorInside = (from, to) => state.selection.ranges.some((r) => r.to > from && r.from < to);
  const withSpace = (to) => (state.sliceDoc(to, to + 1) === ' ' ? to + 1 : to);

  tree.iterate({
    enter(node) {
      const { name, from, to } = node;
      if (name === 'FencedCode' || name === 'CodeBlock') {
        code.push([from, to]);
        lineClass(from, to, 'cm-codeblock');
        return false;
      }
      if (name === 'InlineCode') code.push([from, to]);
      const heading = /^ATXHeading(\d)$/.exec(name);
      if (heading) lineClass(from, from, `cm-h${heading[1]}`);
      if (name === 'Blockquote') lineClass(from, to, 'cm-quote');

      if (name === 'Link') {
        const marks = [];
        let url = null;
        for (let c = node.node.firstChild; c; c = c.nextSibling) {
          if (c.name === 'LinkMark') marks.push(c);
          if (c.name === 'URL') url = state.sliceDoc(c.from, c.to);
        }
        if (url && marks.length >= 2) {
          linked.push([from, to]);
          out.push({ from: marks[0].to, to: marks[1].from, type: 'link', url });
          if (!isActive(from)) {
            out.push({ from: marks[0].from, to: marks[0].to, type: 'hide' });
            out.push({ from: marks[1].from, to, type: 'hide' });
          }
        }
        return false;
      }

      // Like Obsidian, list markers and checkboxes stay rendered on the cursor line and only
      // turn back into source when the cursor is inside them.
      if (name === 'ListMark' && node.node.parent?.parent?.name === 'BulletList') {
        const task = node.node.parent.getChild('Task')?.getChild('TaskMarker');
        const end = task ? task.to : to;
        if (!cursorInside(from, end)) {
          out.push(task ? { from, to: withSpace(to), type: 'hide' } : { from, to, type: 'bullet' });
          if (task) out.push({ from: task.from, to: task.to, type: 'task', checked: /x/i.test(state.sliceDoc(task.from + 1, task.to - 1)) });
        }
        return;
      }
      if (isActive(from)) return;
      if (name === 'HeaderMark' && node.node.parent?.name.startsWith('ATXHeading')) {
        out.push({ from, to: withSpace(to), type: 'hide' });
      } else if (name === 'QuoteMark') {
        out.push({ from, to: withSpace(to), type: 'hide' });
      } else if (name === 'EmphasisMark' || name === 'StrikethroughMark') {
        out.push({ from, to, type: 'hide' });
      } else if (name === 'CodeMark' && node.node.parent?.name === 'InlineCode') {
        out.push({ from, to, type: 'hide' });
      }
    },
  });

  const inside = (spans, a, b) => spans.some(([f, t]) => a < t && b > f);
  const doc = state.doc.toString();
  for (const m of doc.matchAll(WIKILINK)) {
    const from = m.index, to = from + m[0].length;
    if (inside(code, from, to)) continue;
    if (doc[from - 1] === '!') {
      if (!isActive(from)) out.push({ from: from - 1, to, type: 'embed', target: m[1].split('#')[0] });
      continue;
    }
    const textFrom = m[3] ? to - 2 - m[3].length : from + 2;
    out.push({ from: textFrom, to: to - 2, type: 'link', target: m[1].split('#')[0] });
    if (!isActive(from)) {
      out.push({ from, to: textFrom, type: 'hide' });
      out.push({ from: to - 2, to, type: 'hide' });
    }
  }
  for (const m of doc.matchAll(HIGHLIGHT)) {
    const from = m.index, to = from + m[0].length;
    if (inside(code, from, to) || inside(linked, from, to)) continue;
    out.push({ from: from + 2, to: to - 2, type: 'highlight' });
    if (!isActive(from)) {
      out.push({ from, to: from + 2, type: 'hide' });
      out.push({ from: to - 2, to, type: 'hide' });
    }
  }

  for (let n = 1; n <= state.doc.lines; n++) {
    const line = state.doc.line(n);
    const m = TIME.exec(line.text);
    if (m && !inside(code, line.from, line.to)) out.push({ from: line.from + 2, to: line.from + 2 + m[1].length, type: 'time' });
  }

  return out.sort((a, b) => a.from - b.from || a.to - b.to);
}

export function toggleTask(state, from) {
  const mark = state.sliceDoc(from + 1, from + 2);
  return { from: from + 1, to: from + 2, insert: mark === ' ' ? 'x' : ' ' };
}

const continueMarkup = insertNewlineContinueMarkupCommand({ nonTightLists: false });
const BLANK_LINE = /^(\r?\n)[ \t>]*\r?\n/;

// Enter inside a list, Obsidian-style: continue the item, or leave the list from an empty one,
// never inserting a blank line. Returns the transaction, or null when not in a list.
export function newlineInList(state) {
  const single = state.selection.ranges.length === 1;
  let tr = null;
  if (!continueMarkup({ state, dispatch: (t) => { tr = t; } })) return null;
  if (!single) return tr;
  let shift = 0;
  const changes = [];
  tr.changes.iterChanges((fromA, toA, _fromB, _toB, inserted) => {
    let text = inserted.toString();
    const blank = BLANK_LINE.exec(text);
    if (blank) {
      text = blank[1] + text.slice(blank[0].length);
      shift -= blank[0].length - blank[1].length;
    }
    changes.push({ from: fromA, to: toA, insert: text });
  });
  if (!shift) return tr;
  return state.update({
    changes,
    selection: { anchor: tr.selection.main.head + shift },
    scrollIntoView: true,
    userEvent: 'input',
  });
}
