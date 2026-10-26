import { test } from 'node:test';
import assert from 'node:assert/strict';
import { current, isBook, isYear, shift, title, yearOf } from './period.js';

const now = new Date(2026, 9, 19);

test('a note key is a day (YYYY-MM-DD) or a year (YYYY)', () => {
  assert.equal(isYear('2026'), true);
  assert.equal(isYear('2026-10-19'), false);
  assert.equal(yearOf('2026-10-19'), '2026');
});

test('stepping moves by a day for day notes and by a year for year notes', () => {
  assert.equal(shift('2026-12-31', 1), '2027-01-01');
  assert.equal(shift('2026', -1), '2025');
  assert.equal(shift('2026', 1), '2027');
});

test('the current note of each kind is today or this year', () => {
  assert.equal(current('2025-01-01', now), '2026-10-19');
  assert.equal(current('2025', now), '2026');
});

test('the header names the day with its weekday, or the year', () => {
  assert.equal(title('2026-10-19'), '2026-10-19 周一');
  assert.equal(title('2026'), '2026 年');
});

test('a book key names a book note by its vault path; it never steps', () => {
  const key = 'book:Reading/Books/茶馆：成都.md';
  assert.equal(isBook(key), true);
  assert.equal(isBook('2026'), false);
  assert.equal(isYear(key), false);
  assert.equal(title(key), '茶馆：成都');
  assert.equal(shift(key, 1), key);
  assert.equal(current(key, now), key);
});
