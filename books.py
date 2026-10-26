"""Book mode: one catalog of books from the book notes and the book lists the config names."""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

TITLE_MARKS = re.compile(r"[《》“”‘’\"'「」（）()\[\]【】]")
BRACKETED = re.compile(r"\[[^\]]*\]|【[^】]*】|\([^)]*\)|（[^）]*）")
FRONTMATTER = re.compile(r"\A---\n(.*?)^---[ \t]*(?:\n|\Z)", re.S | re.M)
FIELD = re.compile(r"^([\w-]+):[ \t]*(.*)$", re.M)


def normalize_title(s):
    """reading-capture's rule for book titles: drop the brackets and quotes, full-width colons."""
    return TITLE_MARKS.sub("", s or "").strip().replace(":", "：")


def primary_author(s):
    """The first author, without nationality marks or spaces: enough to tell two same-titled books apart."""
    first = (s or "").split("/")[0]
    first = re.sub(r"\s+", "", BRACKETED.sub("", first))
    return re.sub(r"[.•・]", "·", first)


def cover_cache_name(key):
    return re.sub(r"[:/]", "_", key) + ".jpg"


def read_frontmatter(text):
    """Top-level `key: value` fields (quotes stripped, null or empty as None) and the body after them."""
    m = FRONTMATTER.match(text)
    if not m:
        return {}, text
    fields = {}
    for key, value in FIELD.findall(m.group(1)):
        value = value.strip().strip("'\"")
        fields[key] = None if value in ("", "null", "~") else value
    return fields, text[m.end():]


def _read_list(source):
    try:
        items = json.loads(Path(source.path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        print(f"跳过书目来源 {source.path}：{err}", file=sys.stderr)
        return []
    if not isinstance(items, list):
        print(f"跳过书目来源 {source.path}：不是书的列表", file=sys.stderr)
        return []
    return [item for item in items if isinstance(item, dict) and item.get("title")]


def _entry(title, author, source, douban_id=None, cover_url=None, weread_id=None):
    return {"title": title, "author": author or None, "doubanId": douban_id or None, "aliases": [],
            "coverUrl": cover_url or None, "source": source, "note": None, "text": "",
            "_weread": weread_id, "_title": normalize_title(title), "_author": primary_author(author)}


def _from_source(source):
    items = _read_list(source)
    if source.kind == "douban":
        if any(item.get("wish_date") for item in items):
            items = sorted(items, key=lambda i: i.get("wish_date") or "", reverse=True)
        return [_entry(i["title"], i.get("author"), source.label, str(i.get("douban_id") or "") or None,
                       i.get("cover_url")) for i in items]
    items = sorted(items, key=lambda i: i.get("lastReadUpdate") or 0, reverse=True)
    books = [_entry(re.sub(r"^《([^》]*)》", r"\1", i["title"]), i.get("author"), source.label,
                    cover_url=i.get("cover"), weread_id=i.get("bookId")) for i in items]
    for book in books:
        book["_bare"] = normalize_title(BRACKETED.sub("", book["title"]))
    return books


class _Catalog:
    """Books in order, findable by Douban id (aliases too) and by normalized title."""

    def __init__(self):
        self.books, self.by_id, self.by_title = [], {}, {}

    def same(self, book):
        if book["doubanId"] and book["doubanId"] in self.by_id:
            return self.by_id[book["doubanId"]]
        # A WeRead title may carry an edition note, 卡拉马佐夫兄弟（果麦经典）: try it without as well.
        for title in dict.fromkeys([book["_title"], book.get("_bare")]):
            for other in self.by_title.get(title, []) if title else []:
                if not book["_author"] or not other["_author"] or book["_author"] == other["_author"]:
                    return other
        return None

    def add(self, book):
        other = self.same(book)
        if other is None:
            self.books.append(book)
            self.by_title.setdefault(book["_title"], []).append(book)
            other = book
        else:
            for k, v in book.items():
                if other.get(k) in (None, "") and v:
                    other[k] = v
            if book["doubanId"] and book["doubanId"] != other["doubanId"] and book["doubanId"] not in other["aliases"]:
                other["aliases"].append(book["doubanId"])
        for i in [other["doubanId"], *other["aliases"]]:
            if i:
                self.by_id[i] = other


def _candidates(catalog, note):
    """reading-capture's matching, in order: Douban id, the same title, a title the note extends with a subtitle."""
    if note["doubanId"]:
        hit = catalog.by_id.get(note["doubanId"])
        if hit:
            return [hit]
    fits = lambda b: not note["_author"] or not b["_author"] or note["_author"] == b["_author"]
    same = [b for b in catalog.by_title.get(note["_title"], []) if fits(b)]
    if same:
        return same
    title = note["_title"]
    return [b for i, ch in enumerate(title) if ch == "：" for b in catalog.by_title.get(title[:i], []) if fits(b)]


def _match(catalog, note):
    found = [b for b in _candidates(catalog, note) if b["note"] is None]
    if len(found) > 1 and note["_author"]:
        found = [b for b in found if b["_author"] == note["_author"]] or found
    return found[0] if len(found) == 1 else None


def _notes(cfg, vault):
    notes = []
    for path in cfg.folder.glob("*.md"):
        try:
            fields, body = read_frontmatter(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        note = _entry(fields.get("title") or path.stem, fields.get("author"), "笔记", fields.get("douban_id"),
                      fields.get("cover_url"))
        note.update(note=path.relative_to(vault).as_posix(), text=body, _stem=path.stem, _mtime=path.stat().st_mtime)
        notes.append(note)
    return sorted(notes, key=lambda n: n["_mtime"], reverse=True)


def _key(book):
    if book["doubanId"]:
        return "db:" + book["doubanId"]
    if book.get("_weread"):
        return "wr:" + book["_weread"]
    return "note:" + book["_stem"]


def build_catalog(cfg, vault, cache_dir):
    """Every book once: those with a note first (latest edited first), then the lists in config order."""
    catalog = _Catalog()
    for source in cfg.sources:
        for book in _from_source(source):
            catalog.add(book)
    with_notes = []
    for note in _notes(cfg, Path(vault)):
        book = _match(catalog, note)
        if book is None:
            with_notes.append(note)
        else:
            book.update(note=note["note"], text=note["text"])
            with_notes.append(book)
    rest = [b for b in catalog.books if b["note"] is None]
    out = []
    for book in with_notes + rest:
        key = _key(book)
        cover = Path(cache_dir) / "covers" / cover_cache_name(key)
        out.append({"key": key, **{k: v for k, v in book.items() if not k.startswith("_")},
                    "cover": str(cover) if cover.exists() else None})
    return out


# ---- a book's note ----

UNSAFE = str.maketrans({"/": "／", "\\": "＼", ":": "：", "*": "＊", "?": "？", '"': "＂", "<": "＜", ">": "＞", "|": "｜"})

DEFAULT_TEMPLATE = """---
title: {{title}}
author: {{author}}
cover: {{cover}}
douban_id: {{douban_id}}
douban_url: {{douban_url}}
created: {{date}}
---

# {{title}}

## {{section}}
"""


def safe_name(title):
    """A note's file name: the normalized title with the characters a file name can't hold made full-width."""
    return normalize_title(title).translate(UNSAFE).lstrip(".").strip() or "未命名"


def note_rel_for(book, cfg, vault):
    """Where a book's note is, or would be: the title, plus the author when another book has that name."""
    if book.get("note"):
        return book["note"]
    folder = Path(cfg.folder).relative_to(vault).as_posix()
    name = safe_name(book["title"])
    path = Path(cfg.folder) / f"{name}.md"
    if path.exists():
        owner = read_frontmatter(path.read_text(encoding="utf-8"))[0].get("douban_id")
        if owner and owner != book.get("doubanId") and owner not in (book.get("aliases") or []):
            name = f"{name} ({primary_author(book.get('author')) or book.get('doubanId') or 2})"
    return f"{folder}/{name}.md"


def cover_rel_for(cfg, vault, note_rel):
    folder = Path(cfg.folder).relative_to(vault).as_posix()
    return f"{folder}/{cfg.cover_folder}/{Path(note_rel).stem}.jpg"


def render_book_template(cfg, book, cover_rel, day):
    """A new note: the configured template (or a plain one) with each placeholder as a ready YAML value."""
    from settings import render_template

    template = cfg.template
    text = template.read_text(encoding="utf-8") if template and template.is_file() else DEFAULT_TEMPLATE
    douban_id = book.get("doubanId")
    values = {
        "author": book.get("author") or "null",
        "cover": f'"[[{cover_rel}]]"' if cover_rel else "null",
        "douban_id": f'"{douban_id}"' if douban_id else "null",
        "douban_url": f"https://book.douban.com/subject/{douban_id}/" if douban_id else "null",
        "section": cfg.section,
    }
    for name, value in values.items():
        text = text.replace("{{" + name + "}}", value)
    return render_template(text, day, book["title"])


# ---- covers and Douban search ----

USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
              "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")
DOUBAN_SIZE = re.compile(r"(/view/subject/)[^/]+(/public/)")
SUGGEST = "https://book.douban.com/j/subject_suggest?q="


class SearchError(Exception):
    pass


def fetch(url, timeout):
    """GET a URL the way a browser on douban.com would; Douban's images refuse other referrers."""
    headers = {"User-Agent": USER_AGENT}
    host = urllib.parse.urlsplit(url).hostname or ""
    if host.endswith(("douban.com", "doubanio.com")):
        headers["Referer"] = "https://book.douban.com/"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as response:
        return response.read()


def cover_urls(url):
    """A Douban cover large first, then the smaller sizes; anything else as it is."""
    if not DOUBAN_SIZE.search(url):
        return [url]
    return [DOUBAN_SIZE.sub(rf"\g<1>{size}\g<2>", url) for size in ("l", "m", "s")]


def _download(item, folder):
    target = folder / cover_cache_name(item["key"])
    if target.exists():
        return str(target)
    for url in cover_urls(item["url"]):
        try:
            data = fetch(url, 10)
        except (OSError, ValueError):
            continue
        if data:
            tmp = target.with_suffix(".tmp")
            tmp.write_bytes(data)
            tmp.replace(target)
            return str(target)
    return None


def download_covers(items, cache_dir, workers=4):
    """Covers into the cache, a few at a time: {key: path, or None when no size could be fetched}."""
    folder = Path(cache_dir) / "covers"
    folder.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        paths = list(pool.map(lambda item: _download(item, folder), items))
    return {item["key"]: path for item, path in zip(items, paths)}


def douban_search(q, cache_dir):
    """Books Douban suggests for a query, as catalog entries."""
    try:
        results = json.loads(fetch(SUGGEST + urllib.parse.quote_plus(q), 5))
    except (OSError, ValueError) as err:
        raise SearchError(str(err)) from err
    books = []
    for r in results if isinstance(results, list) else []:
        if r.get("type") != "b" or not r.get("id"):
            continue
        key = f"db:{r['id']}"
        cover = Path(cache_dir) / "covers" / cover_cache_name(key)
        books.append({"key": key, "title": r.get("title") or "", "author": r.get("author_name") or None,
                      "doubanId": str(r["id"]), "aliases": [], "coverUrl": r.get("pic") or None,
                      "cover": str(cover) if cover.exists() else None, "source": "豆瓣搜索", "note": None, "text": ""})
    return books
