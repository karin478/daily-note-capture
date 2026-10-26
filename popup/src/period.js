// The panel edits three kinds of note, named by key: a day's (YYYY-MM-DD), a year's (YYYY) and a book's
// (book: + its path in the vault).
import { isoDay, shiftDay, weekday } from './timeline.js';

export const isYear = (key) => /^\d{4}$/.test(key);
export const isBook = (key) => key.startsWith('book:');
export const yearOf = (key) => key.slice(0, 4);

export const shift = (key, delta) => (isBook(key) ? key : isYear(key) ? String(Number(key) + delta) : shiftDay(key, delta));

// Today's note, or this year's: the same kind as `key`. A book is always itself.
export const current = (key, now = new Date()) => (isBook(key) ? key : isYear(key) ? String(now.getFullYear()) : isoDay(now));

const bookName = (key) => key.slice(key.lastIndexOf('/') + 1).replace(/\.md$/, '');
export const title = (key) => (isBook(key) ? bookName(key) : isYear(key) ? `${key} 年` : `${key} ${weekday(key)}`);
