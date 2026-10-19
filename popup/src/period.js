// The panel edits two kinds of note, named by key: a day's (YYYY-MM-DD) and a year's (YYYY).
import { isoDay, shiftDay, weekday } from './timeline.js';

export const isYear = (key) => /^\d{4}$/.test(key);
export const yearOf = (key) => key.slice(0, 4);

export const shift = (key, delta) => (isYear(key) ? String(Number(key) + delta) : shiftDay(key, delta));

// Today's note, or this year's: the same kind as `key`.
export const current = (key, now = new Date()) => (isYear(key) ? String(now.getFullYear()) : isoDay(now));

export const title = (key) => (isYear(key) ? `${key} 年` : `${key} ${weekday(key)}`);
