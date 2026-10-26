import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mergeEdit } from './merge.js';

const BASE = '## 边读边想\n\n### 2026-10-26\n\n\n## 我的原子笔记\n- [[康威定律]]\n';
const LOCAL = '## 边读边想\n\n### 2026-10-26\n加人反而更慢。\n\n## 我的原子笔记\n- [[康威定律]]\n';

test('words typed while another program appended elsewhere are kept on top of its change', () => {
  const current = BASE + '- [[外部追加]]\n';
  const merged = mergeEdit(BASE, LOCAL, current);
  assert.equal(merged.body, LOCAL + '- [[外部追加]]\n');
  assert.equal(merged.inserted, '加人反而更慢。');
});

test('a change before the typing shifts where the typing goes', () => {
  const current = '---\nupdated: x\n---\n' + BASE;
  assert.equal(mergeEdit(BASE, LOCAL, current).body, '---\nupdated: x\n---\n' + LOCAL);
  assert.equal(mergeEdit(BASE, LOCAL, current).shift, '---\nupdated: x\n---\n'.length);
});

test('when the other change touched the same spot there is no merge', () => {
  const current = BASE.replace('### 2026-10-26\n\n', '### 2026-10-26\n别处写的\n');
  assert.equal(mergeEdit(BASE, LOCAL, current), null);
});

test('nothing typed means nothing to merge', () => {
  assert.equal(mergeEdit(BASE, BASE, BASE + 'x'), null);
});
