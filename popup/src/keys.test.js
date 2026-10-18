import { test } from 'node:test';
import assert from 'node:assert/strict';
import { dayStep } from './keys.js';

const key = (code, mods = {}) => ({ code, metaKey: true, ctrlKey: false, altKey: false, shiftKey: false, ...mods });

test('⌘ with the [ ] keys steps a day, whatever the input method types there (【 】)', () => {
  assert.equal(dayStep(key('BracketLeft')), -1);
  assert.equal(dayStep(key('BracketRight')), 1);
});

test('other combinations are not day steps', () => {
  assert.equal(dayStep(key('BracketLeft', { metaKey: false })), null);
  assert.equal(dayStep(key('BracketLeft', { shiftKey: true })), null);
  assert.equal(dayStep(key('BracketRight', { altKey: true })), null);
  assert.equal(dayStep(key('KeyT')), null);
});
