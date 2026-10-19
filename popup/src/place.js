// Where a note opens: where you left it (cursor and scroll), or at the end the first time.
export function placeFor(saved, length) {
  if (!saved) return { anchor: length, head: length, scrollTop: null };
  const clamp = (n) => Math.min(n, length);
  return { anchor: clamp(saved.anchor), head: clamp(saved.head), scrollTop: saved.scrollTop };
}
