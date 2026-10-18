import { test } from 'node:test';
import assert from 'node:assert/strict';
import { EditorState, EditorSelection } from '@codemirror/state';
import { previewRanges, toggleTask, markdownExtension, newlineInList } from './preview.js';

// Build a state with the cursor at the end of the given line (1-based), default: an extra empty last line.
function stateOf(doc, cursorLine) {
  const state = EditorState.create({ doc, extensions: [markdownExtension()] });
  const line = state.doc.line(cursorLine ?? state.doc.lines);
  return state.update({ selection: EditorSelection.cursor(line.to) }).state;
}

const pick = (state, type) =>
  previewRanges(state).filter((r) => r.type === type).map((r) => state.sliceDoc(r.from, r.to));

test('hides emphasis, strikethrough and inline-code marks off the cursor line', () => {
  const s = stateOf('**粗** *斜* ~~删~~ `code`\n');
  assert.deepEqual(pick(s, 'hide'), ['**', '**', '*', '*', '~~', '~~', '`', '`']);
});

test('reveals syntax on the cursor line', () => {
  const s = stateOf('**粗**\n', 1);
  assert.deepEqual(pick(s, 'hide'), []);
});

test('hides heading marks with their trailing space and styles the line', () => {
  const s = stateOf('## 标题\n');
  assert.deepEqual(pick(s, 'hide'), ['## ']);
  assert.deepEqual(previewRanges(s).filter((r) => r.type === 'line').map((r) => r.cls), ['cm-h2']);
});

test('replaces bullet marks with a dot widget', () => {
  const s = stateOf('- a\n\t- b\n');
  assert.deepEqual(pick(s, 'bullet'), ['-', '-']);
});

test('ordered list numbers stay as they are', () => {
  const s = stateOf('1. a\n');
  assert.deepEqual(pick(s, 'bullet'), []);
});

test('renders task markers as checkboxes and hides their list mark', () => {
  const s = stateOf('- [ ] todo\n- [x] done\n');
  const tasks = previewRanges(s).filter((r) => r.type === 'task');
  assert.deepEqual(tasks.map((r) => [s.sliceDoc(r.from, r.to), r.checked]), [['[ ]', false], ['[x]', true]]);
  assert.deepEqual(pick(s, 'bullet'), []);
  assert.deepEqual(pick(s, 'hide'), ['- ', '- ']);
});

test('wikilinks hide their brackets and alias target', () => {
  const s = stateOf('看 [[双链]] 和 [[页面#标题|别名]]\n');
  assert.deepEqual(pick(s, 'hide'), ['[[', ']]', '[[页面#标题|', ']]']);
  assert.deepEqual(pick(s, 'link'), ['双链', '别名']);
});

test('markdown links show only their text', () => {
  const s = stateOf('[文字](https://x.y)\n');
  assert.deepEqual(pick(s, 'hide'), ['[', '](https://x.y)']);
  assert.deepEqual(pick(s, 'link'), ['文字']);
});

test('==highlight== hides its marks', () => {
  const s = stateOf('==重点==\n');
  assert.deepEqual(pick(s, 'hide'), ['==', '==']);
  assert.deepEqual(pick(s, 'highlight'), ['重点']);
});

test('nothing inside fenced code is decorated except the code line style', () => {
  const s = stateOf('```py\n# comment **x**\n```\n');
  assert.deepEqual(pick(s, 'hide'), []);
  assert.equal(previewRanges(s).filter((r) => r.type === 'line' && r.cls === 'cm-codeblock').length, 3);
});

test('quote marks are hidden and the line styled', () => {
  const s = stateOf('> 引用\n');
  assert.deepEqual(pick(s, 'hide'), ['> ']);
  assert.deepEqual(previewRanges(s).filter((r) => r.type === 'line').map((r) => r.cls), ['cm-quote']);
});

test('toggleTask flips the checkbox character', () => {
  const s = stateOf('- [ ] a\n- [x] b\n');
  const [open, done] = previewRanges(s).filter((r) => r.type === 'task');
  assert.deepEqual(toggleTask(s, open.from), { from: open.from + 1, to: open.from + 2, insert: 'x' });
  assert.deepEqual(toggleTask(s, done.from), { from: done.from + 1, to: done.from + 2, insert: ' ' });
});

test('bullets and checkboxes stay rendered on the cursor line', () => {
  const s = stateOf('- a\n- [ ] b\n', 2);
  assert.deepEqual(pick(s, 'bullet'), ['-']);
  assert.equal(previewRanges(s).filter((r) => r.type === 'task').length, 1);
});

test('a freshly typed task renders while the cursor sits after it', () => {
  const s = stateOf('- [ ] ', 1);
  assert.equal(previewRanges(s).filter((r) => r.type === 'task').length, 1);
});

test('task markup is revealed when the cursor is inside it', () => {
  const base = EditorState.create({ doc: '- [ ] b', extensions: [markdownExtension()] });
  const s = base.update({ selection: EditorSelection.cursor(3) }).state;
  assert.equal(previewRanges(s).filter((r) => r.type === 'task').length, 0);
});

// Press Enter at the end of the document and return the new text.
function enter(doc) {
  const s = EditorState.create({ doc, extensions: [markdownExtension()], selection: EditorSelection.cursor(doc.length) });
  const tr = newlineInList(s);
  return tr && { doc: tr.state.doc.toString(), cursor: tr.state.selection.main.head };
}

test('Enter continues a bullet list without a blank line', () => {
  assert.deepEqual(enter('- a'), { doc: '- a\n- ', cursor: 6 });
});

test('Enter continues a task list with an empty task', () => {
  assert.deepEqual(enter('- [ ] a'), { doc: '- [ ] a\n- [ ] ', cursor: 14 });
});

test('Enter continues and renumbers an ordered list', () => {
  assert.deepEqual(enter('1. a'), { doc: '1. a\n2. ', cursor: 8 });
});

test('Enter on an empty item leaves the list instead of adding a blank line', () => {
  assert.deepEqual(enter('- a\n- '), { doc: '- a\n', cursor: 4 });
});

test('Enter in a list that already has blank lines adds no new blank line', () => {
  assert.deepEqual(enter('- a\n\n- b'), { doc: '- a\n\n- b\n- ', cursor: 11 });
});

test('Enter outside a list is left to the default handler', () => {
  assert.equal(enter('plain'), null);
});
