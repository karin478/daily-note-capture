import { test } from 'node:test';
import assert from 'node:assert/strict';
import { placeFor } from './place.js';

test('a note opened for the first time starts at the end, ready to write', () => {
  assert.deepEqual(placeFor(undefined, 40), { anchor: 40, head: 40, scrollTop: null });
});

test('a note you were in before opens where you left the cursor and the scroll', () => {
  assert.deepEqual(placeFor({ anchor: 3, head: 9, scrollTop: 120 }, 40), { anchor: 3, head: 9, scrollTop: 120 });
});

test('a note that got shorter elsewhere keeps the cursor inside it', () => {
  assert.deepEqual(placeFor({ anchor: 30, head: 50, scrollTop: 120 }, 20), { anchor: 20, head: 20, scrollTop: 120 });
});
