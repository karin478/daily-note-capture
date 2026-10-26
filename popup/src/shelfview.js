// The book shelf: a search box over a grid of covers. Covers are fetched as they scroll into view, and
// Douban's suggestions join the results once you stop typing.
import { arrange, fileUrl, mergeDouban, normalizeQuery, placeholderHue, withOpened } from './shelf.js';

const BATCH = 60; // cards rendered at a time, more as you scroll
const COVER_BATCH = 20; // covers asked for at a time
const DOUBAN_DELAY = 400;

export function createShelf(root, { post, onOpen }) {
  const search = root.querySelector('#shelf-search');
  const list = root.querySelector('#shelf-list');
  let catalog = [], books = [], recents = {}, doubanOn = true;
  const fromDouban = new Map(); // books opened from Douban's results this session
  let douban = null; // { q, items } or { q, error: true } for the current query
  let doubanTimer = null;
  let entries = [], rendered = 0, grid = null, first = null;

  // ---- covers: ask for the ones on screen, one request at a time ----
  const asked = new Set();
  const wanted = new Map(); // key -> url
  let coverTimer = null, coverInFlight = false;
  const sendCovers = () => {
    if (coverInFlight || !wanted.size) return;
    const items = [...wanted].slice(0, COVER_BATCH).map(([key, url]) => ({ key, url }));
    for (const { key } of items) wanted.delete(key);
    coverInFlight = true;
    post({ action: 'covers', items });
  };
  const seen = new IntersectionObserver((hits) => {
    for (const hit of hits) {
      if (!hit.isIntersecting) continue;
      const { key, url } = hit.target.dataset;
      seen.unobserve(hit.target);
      if (asked.has(key)) continue;
      asked.add(key);
      wanted.set(key, url);
    }
    clearTimeout(coverTimer);
    coverTimer = setTimeout(sendCovers, 100);
  }, { root: list, rootMargin: '200px' });

  function cover(book) {
    if (book.cover) {
      const img = document.createElement('img');
      img.className = 'shelf-cover';
      img.src = fileUrl(book.cover);
      img.alt = '';
      return img;
    }
    const hue = placeholderHue(book.title);
    const box = document.createElement('div');
    box.className = 'shelf-cover shelf-placeholder';
    box.style.background = `linear-gradient(160deg, hsl(${hue} 45% 70%), hsl(${hue} 45% 52%))`;
    box.textContent = book.title;
    if (book.coverUrl && !asked.has(book.key)) {
      box.dataset.key = book.key;
      box.dataset.url = book.coverUrl;
      seen.observe(box);
    }
    return box;
  }

  function card(book) {
    const el = document.createElement('button');
    el.className = 'shelf-book';
    el.dataset.key = book.key;
    el.title = book.author ? `${book.title} · ${book.author}` : book.title;
    const name = document.createElement('div');
    name.className = 'shelf-title';
    name.textContent = book.title;
    el.append(cover(book), name);
    el.addEventListener('click', () => onOpen(book));
    return el;
  }

  // ---- rendering: a flat list of headings, notes and books, drawn in batches ----
  const more = new IntersectionObserver((hits) => { if (hits.some((h) => h.isIntersecting)) renderMore(); }, { root: list });
  const sentinel = document.createElement('div');
  sentinel.className = 'shelf-end';

  function renderMore() {
    let drawn = 0;
    while (rendered < entries.length && drawn < BATCH) {
      const e = entries[rendered++];
      if (e.heading !== undefined || e.message !== undefined) {
        const head = document.createElement('div');
        head.className = e.message !== undefined ? 'shelf-message' : 'shelf-heading';
        head.textContent = e.message ?? e.heading;
        list.insertBefore(head, sentinel);
        grid = null;
        continue;
      }
      if (!grid) {
        grid = document.createElement('div');
        grid.className = 'shelf-grid';
        list.insertBefore(grid, sentinel);
      }
      grid.append(card(e.book));
      drawn++;
    }
  }

  function render() {
    const q = search.value;
    const { recent, all } = arrange(books, q, recents);
    entries = [];
    const add = (heading, items) => {
      if (!items.length) return;
      if (heading) entries.push({ heading });
      for (const book of items) entries.push({ book });
    };
    let found = [];
    if (!normalizeQuery(q)) {
      add('最近', recent);
      add(recent.length ? '全部' : '', all);
    } else {
      add('', all);
      if (!all.length) entries.push({ message: '本地没有找到' });
      if (douban?.q === q.trim()) {
        found = douban.error ? [] : mergeDouban(books, douban.items);
        if (douban.error) entries.push({ heading: '豆瓣搜索' }, { message: '豆瓣搜索不可用' });
        else add('豆瓣搜索', found);
      }
    }
    first = all[0] ?? found[0] ?? null;
    list.replaceChildren(sentinel);
    rendered = 0;
    grid = null;
    renderMore();
    list.scrollTop = 0;
  }

  function askDouban() {
    clearTimeout(doubanTimer);
    const q = search.value.trim();
    if (!doubanOn || !normalizeQuery(q)) return;
    doubanTimer = setTimeout(() => post({ action: 'doubanSearch', q }), DOUBAN_DELAY);
  }

  search.addEventListener('input', (e) => {
    render();
    if (!e.isComposing) askDouban();
  });
  search.addEventListener('compositionend', askDouban);
  search.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.isComposing && first) {
      e.preventDefault();
      onOpen(first);
    }
  });
  more.observe(sentinel);

  return {
    setBooks(next, searchOn) {
      catalog = next;
      books = withOpened(catalog, [...fromDouban.values()]);
      doubanOn = searchOn !== false;
      render();
    },
    setRecents(next) {
      recents = next || {};
      render();
    },
    opened(book) {
      recents = { ...recents, [book.key]: Date.now() / 1000 };
      if (book.source === '豆瓣搜索') fromDouban.set(book.key, book);
      books = withOpened(catalog, [...fromDouban.values()]);
    },
    coversLoaded(paths) {
      coverInFlight = false;
      for (const [key, path] of Object.entries(paths || {})) {
        if (!path) continue;
        for (const book of [...books, ...(douban?.items ?? [])]) if (book.key === key) book.cover = path;
        for (const el of list.querySelectorAll(`.shelf-placeholder[data-key="${CSS.escape(key)}"]`)) {
          const img = document.createElement('img');
          img.className = 'shelf-cover';
          img.src = fileUrl(path);
          img.alt = '';
          el.replaceWith(img);
        }
      }
      sendCovers();
    },
    doubanResults(result) {
      if (!result || result.q !== search.value.trim()) return;
      douban = result;
      render();
    },
    reset() {
      search.value = '';
      douban = null;
      render();
    },
    focus() {
      search.focus();
    },
  };
}
