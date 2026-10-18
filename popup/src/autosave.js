// What to do when a save comes back. The backend writes the body exactly, so compare exactly.

// sent: the body that was saved; stored: what the file now holds; now: the editor.
export function afterSave({ sent, stored, now }) {
  const mismatch = stored !== sent;
  // base is always what the file holds, so the next save's conflict check passes. Text that was
  // already sent is never saved again, even if the file disagrees — that loop once duplicated a note.
  return { base: stored, again: now !== sent && now !== stored, mismatch };
}
