import { test } from 'node:test';
import assert from 'node:assert/strict';
import { stepZoom, ZOOM_LEVELS } from './zoom.js';

test('zoom steps through the browser levels', () => {
  assert.equal(stepZoom(1, 1), 1.1);
  assert.equal(stepZoom(1.1, 1), 1.25);
  assert.equal(stepZoom(1, -1), 0.9);
  assert.equal(stepZoom(0.9, -1), 0.8);
});

test('zoom stops at the smallest and largest level', () => {
  assert.equal(stepZoom(ZOOM_LEVELS[0], -1), ZOOM_LEVELS[0]);
  assert.equal(stepZoom(ZOOM_LEVELS.at(-1), 1), ZOOM_LEVELS.at(-1));
});

test('⌘0 goes back to 100%', () => {
  assert.equal(stepZoom(1.75, 0), 1);
});

test('a level between steps moves to the next step in that direction', () => {
  assert.equal(stepZoom(1.05, 1), 1.1);
  assert.equal(stepZoom(1.05, -1), 1);
});
