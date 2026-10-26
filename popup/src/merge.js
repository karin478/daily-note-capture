// When a save finds the note changed elsewhere (say reading-capture appended to it), keep what was just
// typed: put the one edited stretch back into the newer text, if the text around it is still there.

const CONTEXT = 40; // characters on each side that must still match, exactly once

// base: the note as the panel last saved or loaded it; local: the editor now; current: the file now.
// Returns { body, inserted, shift } — shift is how far the edit moved — or null when it can't be kept safely.
export function mergeEdit(base, local, current) {
  let p = 0;
  while (p < base.length && p < local.length && base[p] === local[p]) p++;
  let s = 0;
  while (s < base.length - p && s < local.length - p && base[base.length - 1 - s] === local[local.length - 1 - s]) s++;
  const removed = base.slice(p, base.length - s);
  const inserted = local.slice(p, local.length - s);
  if (!removed && !inserted) return null;
  const left = base.slice(Math.max(0, p - CONTEXT), p);
  const needle = left + removed + base.slice(base.length - s, base.length - s + CONTEXT);
  const at = current.indexOf(needle);
  if (at < 0 || current.indexOf(needle, at + 1) >= 0) return null;
  const start = at + left.length;
  return { body: current.slice(0, start) + inserted + current.slice(start + removed.length), inserted, shift: start - p };
}
