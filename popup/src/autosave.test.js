import { test } from 'node:test';
import assert from 'node:assert/strict';
import { afterSave } from './autosave.js';

test('a save that stored what was sent leaves nothing to do', () => {
  assert.deepEqual(afterSave({ sent: '- a\n', stored: '- a\n', now: '- a\n' }), { base: '- a\n', again: false, mismatch: false });
});

test('typing during a save saves again against what the file now holds', () => {
  assert.deepEqual(afterSave({ sent: '- a', stored: '- a', now: '- ab' }), { base: '- a', again: true, mismatch: false });
});

test('a file that stored something else is reported, never re-saved in a loop', () => {
  assert.deepEqual(afterSave({ sent: '- a\n# 阅读\n- b', stored: '- a', now: '- a\n# 阅读\n- b' }),
    { base: '- a', again: false, mismatch: true });
});

test('whitespace typed during a save still counts: base stays what the file holds', () => {
  // A space or blank line typed while the save was in flight must not make base differ from the
  // file, or the next save is refused as a conflict and the panel reloads over your typing.
  assert.deepEqual(afterSave({ sent: '- 看', stored: '- 看', now: '- 看 ' }), { base: '- 看', again: true, mismatch: false });
  assert.deepEqual(afterSave({ sent: '- 要\n', stored: '- 要\n', now: '- 要\n\n' }), { base: '- 要\n', again: true, mismatch: false });
});
