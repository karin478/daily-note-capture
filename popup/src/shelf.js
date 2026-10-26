// The book shelf's order: opened books first, and search by title, author and note text.

// The same marks books.normalize_title drops, then no spaces and no case, so a query matches loosely.
const MARKS = /[《》“”‘’"'「」（）()[\]【】]/g;
export const normalizeQuery = (q) => (q ?? '').replace(MARKS, '').replace(/:/g, '：').replace(/\s+/g, '').toLowerCase();

// 0 the title starts with the query, 1 the title has it, 2 the author has it, 3 the note text has it.
function rank(book, q) {
  const title = normalizeQuery(book.title);
  if (title.startsWith(q)) return 0;
  if (title.includes(q)) return 1;
  if (normalizeQuery(book.author).includes(q)) return 2;
  if (normalizeQuery(book.text).includes(q)) return 3;
  return -1;
}

// books: the catalog in its own order; recents: { key: when it was last opened }.
export function arrange(books, query, recents) {
  const q = normalizeQuery(query);
  const opened = (b) => recents[b.key] ?? -Infinity;
  if (!q) {
    const recent = books.filter((b) => b.key in recents).sort((a, b) => opened(b) - opened(a));
    return { recent, all: books.filter((b) => !(b.key in recents)) };
  }
  const hits = books.map((book, i) => ({ book, i, r: rank(book, q) })).filter((h) => h.r >= 0);
  hits.sort((a, b) => a.r - b.r || opened(b.book) - opened(a.book) || a.i - b.i);
  return { recent: [], all: hits.map((h) => h.book) };
}

// books.primary_author: the first author, without nationality marks, spaces or dot styles.
export const primaryAuthor = (s) =>
  (s ?? '').split('/')[0].replace(/\[[^\]]*\]|【[^】]*】|\([^)]*\)|（[^）]*）/g, '').replace(/\s+/g, '').replace(/[.•・]/g, '·');

// Douban's suggestions, minus the books the shelf already has: by any of their Douban ids, or as another
// edition (the same title and author, the catalog's rule for one book).
export function mergeDouban(shown, results) {
  const ids = new Set(shown.flatMap((b) => [b.doubanId, ...(b.aliases ?? [])]).filter(Boolean));
  const byTitle = new Map();
  for (const b of shown) {
    const t = normalizeQuery(b.title);
    byTitle.set(t, [...(byTitle.get(t) ?? []), primaryAuthor(b.author)]);
  }
  const edition = (r) => {
    const a = primaryAuthor(r.author);
    return (byTitle.get(normalizeQuery(r.title)) ?? []).some((b) => !a || !b || a === b);
  };
  return results.filter((r) => !ids.has(r.doubanId) && !edition(r));
}

// A cover with no picture gets a colour of its own, the same every time.
export function placeholderHue(title) {
  let h = 0;
  for (const ch of title ?? '') h = (h * 31 + ch.codePointAt(0)) % 360;
  return h;
}

export const fileUrl = (path) => 'file://' + path.split('/').map(encodeURIComponent).join('/');

// Books opened from Douban's results aren't in the catalog until they have a note; keep them on the shelf.
export const withOpened = (books, opened) => {
  const known = new Set(books.map((b) => b.key));
  return [...opened.filter((b) => !known.has(b.key)), ...books];
};
