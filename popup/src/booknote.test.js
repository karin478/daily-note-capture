import { test } from 'node:test';
import assert from 'node:assert/strict';
import { prepareBookNote } from './booknote.js';

const opts = (extra = {}) => ({ section: '边读边想', day: '2026-10-26', fill: {}, remembered: false, ...extra });

test('a note without the section gets it above the first ## heading', () => {
  const body = '---\ntitle: 人月神话\nupdated: 2026-06-13\n---\n\n# 人月神话\n\n## 我的原子笔记\n- 2026-06-13 [[康威定律]]\n\n## 阅读状态\n- 状态：在读\n';
  const out = prepareBookNote(body, opts());
  assert.equal(out.body, '---\ntitle: 人月神话\nupdated: 2026-10-26\n---\n\n# 人月神话\n\n## 边读边想\n\n### 2026-10-26\n\n\n'
    + '## 我的原子笔记\n- 2026-06-13 [[康威定律]]\n\n## 阅读状态\n- 状态：在读\n');
  assert.equal(out.cursor, out.body.indexOf('### 2026-10-26\n') + '### 2026-10-26\n'.length);
  assert.equal(out.newDay, true);
});

test('a note with no ## heading at all gets the section at the end', () => {
  assert.equal(prepareBookNote('# 书\n想法', opts()).body, '# 书\n想法\n\n## 边读边想\n\n### 2026-10-26\n');
});

test("today's heading goes at the end of the section and the cursor under it", () => {
  const out = prepareBookNote('# T\n\n## 边读边想\n\n### 2026-10-25\n昨天的话\n', opts());
  assert.equal(out.body, '# T\n\n## 边读边想\n\n### 2026-10-25\n昨天的话\n\n### 2026-10-26\n');
  assert.equal(out.cursor, out.body.length);
});

test("a new day adds its heading after yesterday's and puts the cursor there", () => {
  const out = prepareBookNote('## 边读边想\n\n### 2026-10-25\n昨天的话\n\n## 我的原子笔记\n', opts({ remembered: true }));
  assert.equal(out.body, '## 边读边想\n\n### 2026-10-25\n昨天的话\n\n### 2026-10-26\n\n\n## 我的原子笔记\n');
  assert.equal(out.newDay, true);
  assert.equal(out.cursor, out.body.indexOf('### 2026-10-26\n') + '### 2026-10-26\n'.length);
});

test('the same day with a remembered place keeps it', () => {
  const body = '---\nupdated: 2026-10-20\n---\n## 边读边想\n\n### 2026-10-26\n今天说的\n';
  const out = prepareBookNote(body, opts({ remembered: true }));
  assert.equal(out.body, body.replace('2026-10-20', '2026-10-26'));
  assert.deepEqual([out.cursor, out.newDay], [-1, false]);
});

test("the same day without a remembered place goes to the end of today's words", () => {
  const out = prepareBookNote('## 边读边想\n\n### 2026-10-26\n今天说的\n\n## 我的原子笔记\n', opts());
  assert.equal(out.cursor, out.body.indexOf('今天说的') + '今天说的'.length);
});

test('null frontmatter fields are filled, set ones are kept', () => {
  const fill = { author: '王笛', cover: '"[[封面/茶馆.jpg]]"', doubanId: '1' };
  const out = prepareBookNote('---\nauthor: null\ncover:\ndouban_id: null\n---\n## 边读边想\n', opts({ fill }));
  assert.ok(out.body.startsWith('---\nauthor: 王笛\ncover: "[[封面/茶馆.jpg]]"\ndouban_id: "1"\n---\n'));
  const kept = prepareBookNote('---\nauthor: 老舍\ncover: "[[x.jpg]]"\n---\n## 边读边想\n', opts({ fill }));
  assert.ok(kept.body.startsWith('---\nauthor: 老舍\ncover: "[[x.jpg]]"\n---\n'));
});

test('updated is set to today only when the field exists', () => {
  assert.ok(!prepareBookNote('---\ntitle: x\n---\n## 边读边想\n', opts()).body.includes('updated'));
});
