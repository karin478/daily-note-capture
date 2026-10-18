import { test } from 'node:test';
import assert from 'node:assert/strict';
import { EditorState, EditorSelection } from '@codemirror/state';
import { CompletionContext } from '@codemirror/autocomplete';
import { indentUnit } from '@codemirror/language';
import { markdownExtension, newlineInList, previewRanges } from './preview.js';
import { clock, isoDay, shiftDay, weekday } from './timeline.js';
import { wikilinkCompletions, tagCompletions } from './completion.js';
import { htmlToMarkdown, linkOverSelection, embedFor, isImage } from './paste.js';

const at = (doc, pos = doc.length, anchor = pos) =>
  EditorState.create({ doc, extensions: [markdownExtension(), indentUnit.of('\t')], selection: EditorSelection.single(anchor, pos) });
const result = (tr) => tr && { doc: tr.state.doc.toString(), cursor: tr.state.selection.main.head };

// ---- timeline ----

test('clock formats hours and minutes with leading zeros', () => {
  assert.equal(clock(new Date(2026, 9, 17, 9, 5)), '09:05');
});

test('Enter on a bullet starts the next one without a time (⌘T adds one)', () => {
  assert.deepEqual(result(newlineInList(at('- 09:00 a'))), { doc: '- 09:00 a\n- ', cursor: 12 });
});

test('times on top-level bullets are marked for styling', () => {
  const s = at('- 14:32 做事\n\t- 09:00 no\n', 0);
  assert.deepEqual(previewRanges(s).filter((r) => r.type === 'time').map((r) => s.sliceDoc(r.from, r.to)), ['14:32']);
});

test('days shift across month and year ends', () => {
  assert.equal(shiftDay('2026-10-31', 1), '2026-11-01');
  assert.equal(shiftDay('2027-01-01', -1), '2026-12-31');
});

test('isoDay uses the local date and weekday names are Chinese', () => {
  assert.equal(isoDay(new Date(2026, 9, 17, 23, 59)), '2026-10-17');
  assert.equal(weekday('2026-10-17'), '周六');
});

// ---- links and embeds ----

test('wikilink ranges carry their target note', () => {
  const s = at('[[页面#标题|别名]] [[双链]]\n');
  assert.deepEqual(previewRanges(s).filter((r) => r.type === 'link').map((r) => r.target), ['页面', '双链']);
});

test('markdown link ranges carry their url', () => {
  const s = at('[文字](https://x.y)\n');
  assert.deepEqual(previewRanges(s).filter((r) => r.type === 'link').map((r) => r.url), ['https://x.y']);
});

test('embeds off the cursor line become embed ranges', () => {
  const s = at('![[Pasted image 1.png]]\n![[a.png]]', 0);
  const embeds = previewRanges(s).filter((r) => r.type === 'embed');
  assert.deepEqual(embeds.map((r) => r.target), ['a.png']);
  assert.deepEqual(previewRanges(s).filter((r) => r.type === 'link'), []);
});

// ---- completion ----

const NOTES = [{ name: '想法', folder: '' }, { name: '2026-10-17', folder: 'Journal/Daily' }];
const FILES = ['想法.md', 'Pasted image 1.png'];

function complete(source, doc, explicit = false) {
  const state = at(doc);
  return source(new CompletionContext(state, doc.length, explicit));
}

test('[[ offers note names that close the link', () => {
  const r = complete((c) => wikilinkCompletions(c, NOTES, FILES), '看 [[想');
  assert.equal(r.from, 4);
  assert.deepEqual(r.options.map((o) => [o.label, o.apply]), [['想法', '想法]]'], ['2026-10-17', '2026-10-17]]']]);
});

test('[[ does not add ]] when it is already there', () => {
  const state = EditorState.create({ doc: '[[]]', selection: EditorSelection.cursor(2) });
  const r = wikilinkCompletions(new CompletionContext(state, 2, false), NOTES, FILES);
  assert.equal(r.options[0].apply, '想法');
});

test('![[ also offers attachments with their extension', () => {
  const r = complete((c) => wikilinkCompletions(c, NOTES, FILES), '![[');
  assert.ok(r.options.some((o) => o.label === 'Pasted image 1.png'));
});

test('# after a space offers tags', () => {
  const r = complete((c) => tagCompletions(c, ['工作', 'life']), '今天 #工');
  assert.equal(r.from, 4);
  assert.deepEqual(r.options.map((o) => o.label), ['工作', 'life']);
});

test('# starting a heading offers nothing', () => {
  assert.equal(complete((c) => tagCompletions(c, ['工作']), '#'), null);
  assert.equal(complete((c) => tagCompletions(c, ['工作']), 'a#b'), null);
});

// ---- paste ----

test('web HTML becomes Obsidian-style markdown', () => {
  const html = '<h2>标题</h2><p>有 <strong>粗</strong> 和 <a href="https://x.y">链接</a></p><ul><li>一</li><li>二</li></ul>';
  assert.equal(htmlToMarkdown(html), '## 标题\n\n有 **粗** 和 [链接](https://x.y)\n\n- 一\n- 二');
});

test('HTML tables, strikethrough and code blocks convert too', () => {
  const md = htmlToMarkdown('<table><tr><th>a</th></tr><tr><td>1</td></tr></table><del>x</del><pre><code>y = 1</code></pre>');
  assert.match(md, /\| a \|/);
  assert.match(md, /~~x~~/);
  assert.match(md, /```\ny = 1\n```/);
});

test('a URL pasted over a selection becomes a link', () => {
  const s = at('看这个', 3, 1);
  assert.deepEqual(result(linkOverSelection(s, 'https://x.y')), { doc: '看[这个](https://x.y)', cursor: 18 });
});

test('non-URL text or an empty selection is not turned into a link', () => {
  assert.equal(linkOverSelection(at('看这个', 3, 1), 'hello'), null);
  assert.equal(linkOverSelection(at('看这个', 3), 'https://x.y'), null);
});

test('attachments embed Obsidian-style', () => {
  assert.equal(embedFor('Pasted image 1.png'), '![[Pasted image 1.png]]');
  assert.ok(isImage('a.PNG') && isImage('b.webp') && !isImage('c.pdf'));
});
