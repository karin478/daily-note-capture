"""Append a markdown entry to the end of today's daily note.

Usage: python capture.py "text"   (or pipe text on stdin)
       python capture.py --ensure   (create today's note if missing, print its vault path)
       python capture.py --get [YYYY-MM-DD]             -> {"date", "body"}: the whole note (creates nothing)
       python capture.py --get YYYY [--create]          the same for a year note; --create makes it if missing
       python capture.py --set DATE BASE BODY           write the whole note; exit 3 if it no longer equals BASE
       python capture.py --attach NAME [EXT] < base64   save a pasted/dropped file where Obsidian puts attachments
       python capture.py --index OUT.json               write note names, file paths and tags for the panel
       python capture.py --doctor                       show which vault, folder, template and format are used
       python capture.py --books OUT.json               write the book catalog for the panel's 书 mode
       python capture.py --covers OUT.json < ITEMS.json  download covers ([{"key", "url"}]) -> {key: path or null}
       python capture.py --douban-search Q              -> {"q", "items"} or {"q", "error": true}
       python capture.py --book-open < BOOK.json         -> {"date": "book:PATH", "body", "exists", "coverRel", "coverSrc"}
       python capture.py --set book:PATH BASE BODY [COVER_SRC COVER_REL]   a book's note, created on its first save

A book's note is named by key "book:" + its path in the vault.

Where the notes are comes from settings.py: the Obsidian vault and its Daily notes settings.
"""
import base64
import json
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

from settings import SetupError
from settings import load as load_settings
from books import (SearchError, build_catalog, cover_rel_for, douban_search, download_cover, download_covers,
                   note_rel_for, render_book_template)
from vault import attachment_folder, pasted_image_name, save_attachment, vault_index

CACHE = Path.home() / "Library/Caches/daily-note-capture"  # the panel's cache; covers live in covers/
PUSH_RE = re.compile(r"^---\s*\n+## 📥 Agent Push", re.M)


def ensure_note(path, template):
    path = Path(path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(template, encoding="utf-8")


def _clean(body):
    return body.strip("\n").rstrip()


def append_note(path, entry, template):
    """Append an entry to the end of a daily note, above an Agent Push block if there is one."""
    entry = _clean(entry)
    if not entry.strip():
        return
    path = Path(path)
    text = path.read_text(encoding="utf-8") if path.exists() else template
    path.parent.mkdir(parents=True, exist_ok=True)
    push = PUSH_RE.search(text)
    head, tail = (text[: push.start()], text[push.start():]) if push else (text, "")
    head = head.rstrip("\n")
    path.write_text((head + "\n\n" if head else "") + entry + "\n" + ("\n" + tail if tail else ""), encoding="utf-8")


def _emit(day, body):
    print(json.dumps({"date": day, "body": body}, ensure_ascii=False))


def _book_path(settings, key):
    """The file a book key names, which must be a note in the book folder."""
    books = _books(settings)
    path = (settings.vault / key[len("book:"):]).resolve()
    if path.suffix != ".md" or Path(books.folder).resolve() not in path.parents:
        print(f"不是书籍文件夹里的笔记：{key}", file=sys.stderr)
        sys.exit(2)
    return path


def _note(settings, key):
    """A note the panel edits, by key: YYYY-MM-DD is a day's note, YYYY a year's, book:PATH a book's."""
    if key.startswith("book:"):
        return _book_path(settings, key), ""  # a new book's template comes from --book-open
    if re.fullmatch(r"\d{4}", key):
        return settings.year_path(int(key)), settings.year_template_text(int(key))
    day = date.fromisoformat(key)
    return settings.note_path(day), settings.template_text(day)


def _whole_note(settings, key):
    """The panel edits a whole note; a missing one shows as the template until saved."""
    path, template = _note(settings, key)
    return path.read_text(encoding="utf-8") if path.exists() else template


def _book_open(settings, book):
    """A book's note as the panel should show it; a book without one gets the template, and no file yet."""
    books, vault = _books(settings), settings.vault
    rel = note_rel_for(book, books, vault)
    path = _book_path(settings, "book:" + rel)
    cover_src = book.get("cover") if book.get("cover") and Path(book["cover"]).is_file() else None
    cover_rel = cover_rel_for(books, vault, rel)
    in_vault = (vault / cover_rel).exists()
    exists = path.exists()
    if not cover_src and not in_vault and book.get("coverUrl"):
        cover_src = download_cover(book["key"], book["coverUrl"], CACHE)  # not scrolled into view yet
    body = path.read_text(encoding="utf-8") if exists else \
        render_book_template(books, book, cover_rel if cover_src or in_vault else None, date.today())
    print(json.dumps({"date": "book:" + rel, "body": body, "exists": exists,
                      "coverRel": cover_rel if cover_src and not in_vault else None,
                      "coverSrc": cover_src}, ensure_ascii=False))


def _copy_cover(settings, body, cover):
    """Saving a book's note copies its cover into the vault once the note points at it."""
    if len(cover) == 2:
        src, rel = Path(cover[0]), cover[1]
        target = settings.vault / rel
        if src.is_file() and not target.exists() and rel in body:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target)


def _doctor(settings):
    template = settings.template
    print(f"vault:    {settings.vault}")
    print(f"日报文件夹: {settings.diary}")
    print(f"模板:     {template or '（无）'}{'' if not template or template.is_file() else '  ⚠️ 文件不存在，新日报会是空白'}")
    print(f"日期格式:  {settings.format}")
    print(f"今天的日报: {settings.note_path(date.today())}")
    print(f"今年的年报: {settings.year_path(date.today().year)}")
    books = settings.books
    if books:
        print(f"书籍文件夹: {books.folder}")
        print(f"书目来源: {len(books.sources)} 个（{'、'.join(s.label for s in books.sources)}）")
        print(f"豆瓣搜索: {'开' if books.douban_search else '关'}")


def _books(settings):
    """Book mode's settings; the book commands stop here when the config has none."""
    if not settings.books:
        print("没有配置书模式（config.json 的 books）", file=sys.stderr)
        sys.exit(2)
    return settings.books


def _write_json(target, data):
    """Big results go through a file: hs.task pipes don't carry hundreds of KB intact."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(target)


def main():
    try:
        settings = load_settings()
    except SetupError as err:
        print(err, file=sys.stderr)
        sys.exit(2)
    run(settings, sys.argv[1:])


def run(settings, args):
    vault = settings.vault
    if args[:1] == ["--doctor"]:
        _doctor(settings)
        return
    if args[:1] == ["--attach"]:
        name = args[1] or pasted_image_name(datetime.now(), args[2] if len(args) > 2 else "png")
        data = base64.b64decode(sys.stdin.read())
        print(json.dumps(save_attachment(attachment_folder(vault, settings.diary), name, data), ensure_ascii=False))
        return
    if args[:1] == ["--index"]:
        _write_json(args[1], {**vault_index(vault), "vaultName": vault.name})
        return
    if args[:1] == ["--books"]:
        books = _books(settings)
        target = Path(args[1])
        _write_json(target, {"books": build_catalog(books, vault, target.parent), "section": books.section,
                             "doubanSearch": books.douban_search})
        return
    if args[:1] == ["--covers"]:
        target = Path(args[1])
        _write_json(target, download_covers(json.loads(sys.stdin.read()), target.parent))
        return
    if args[:1] == ["--douban-search"]:
        q = args[1]
        try:
            print(json.dumps({"q": q, "items": douban_search(q, CACHE)}, ensure_ascii=False))
        except SearchError:
            print(json.dumps({"q": q, "error": True}, ensure_ascii=False))
        return
    if args[:1] == ["--book-open"]:
        _book_open(settings, json.loads(sys.stdin.read()))
        return
    if args[:1] == ["--get"]:
        day = args[1] if len(args) > 1 else date.today().isoformat()
        if "--create" in args[2:]:
            ensure_note(*_note(settings, day))
        _emit(day, _whole_note(settings, day))  # without --create, looking never creates a note; the first save does
        return
    if args[:1] == ["--set"]:
        day, base, body = args[1:4]
        path = _note(settings, day)[0]
        new_book = day.startswith("book:") and not path.exists()  # created on its first save, no conflict to check
        current = _whole_note(settings, day)
        if current != base and not new_book:
            _emit(day, current)
            sys.exit(3)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        if day.startswith("book:"):
            _copy_cover(settings, body, args[4:6])
        _emit(day, body)
        return
    path = settings.note_path(date.today())
    template = settings.template_text(date.today())
    if args == ["--ensure"]:
        ensure_note(path, template)
        print(path.relative_to(vault).as_posix())
        return
    entry = args[0] if args else sys.stdin.read()
    append_note(path, entry, template)


if __name__ == "__main__":
    main()
