import json
import os

import pytest

from books import build_catalog, normalize_title, primary_author
from settings import BookSource, BooksConfig


def douban(id, title, author=None, wish_date=None):
    return {"douban_id": id, "page_url": f"https://book.douban.com/subject/{id}/", "title": title, "author": author,
            "cover_url": f"https://img1.doubanio.com/view/subject/s/public/s{id}.jpg", "wish_date": wish_date}


def weread(id, title, author="", last=0):
    return {"bookId": id, "title": title, "author": author, "cover": f"https://res.weread.qq.com/{id}", "lastReadUpdate": last}


@pytest.fixture
def lib(tmp_path):
    """A vault with a book folder and three book lists; write to them, then call lib.catalog()."""
    class Lib:
        vault = tmp_path
        folder = tmp_path / "Reading" / "Books"
        cache = tmp_path / "cache"
        lists = {"read": [], "wish": [], "weread": []}

        def note(self, name, body="", **fm):
            lines = "".join(f"{k}: {'null' if v is None else v}\n" for k, v in fm.items())
            path = self.folder / f"{name}.md"
            path.write_text(f"---\n{lines}---\n{body}", encoding="utf-8")
            return path

        def write_lists(self):
            data = tmp_path / "data"
            data.mkdir(exist_ok=True)
            for name, items in self.lists.items():
                (data / f"{name}.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")

        def catalog(self, write=True):
            data = tmp_path / "data"
            if write:
                self.write_lists()
            cfg = BooksConfig(folder=self.folder, sources=[BookSource(data / "read.json", "douban", "读过"),
                                                           BookSource(data / "wish.json", "douban", "想读"),
                                                           BookSource(data / "weread.json", "weread", "微信读书")])
            return build_catalog(cfg, self.vault, self.cache)

    lib = Lib()
    lib.folder.mkdir(parents=True)
    lib.lists = {"read": [], "wish": [], "weread": []}
    return lib


def titles(catalog):
    return [b["title"] for b in catalog]


def test_normalize_title():
    assert normalize_title("《收割者》（摇篮系列第 10 部）") == "收割者摇篮系列第 10 部"
    assert normalize_title(" 茶馆: 成都 ") == "茶馆： 成都"


def test_primary_author():
    assert primary_author("[美] 弗雷德里克·布鲁克斯 / 汪颖") == "弗雷德里克·布鲁克斯"
    assert primary_author("【美】小弗雷德里克.P.布鲁克斯") == "小弗雷德里克·P·布鲁克斯"
    assert primary_author(None) == ""


def test_editions_of_one_book_merge(lib):
    lib.lists["read"] = [douban("A", "茶馆", "王笛")]
    lib.lists["wish"] = [douban("B", "茶馆", "王笛")]
    [book] = lib.catalog()
    assert (book["key"], book["aliases"], book["source"]) == ("db:A", ["B"], "读过")


def test_same_title_different_author_stays_apart(lib):
    lib.lists["wish"] = [douban("A", "自我", "甲"), douban("B", "自我", "乙")]
    assert [b["key"] for b in lib.catalog()] == ["db:A", "db:B"]


def test_weread_merges_into_douban_by_title(lib):
    lib.lists["read"] = [douban("1102259", "人月神话", "[美] 弗雷德里克·布鲁克斯")]
    lib.lists["weread"] = [weread("W1", "《人月神话》")]
    [book] = lib.catalog()
    assert book["key"] == "db:1102259"


def test_weread_alone_gets_its_own_key(lib):
    lib.lists["weread"] = [weread("W1", "《收割者》（摇篮系列第 10 部）", "", 5)]
    [book] = lib.catalog()
    assert (book["key"], book["source"], book["coverUrl"]) == ("wr:W1", "微信读书", "https://res.weread.qq.com/W1")


def test_note_matches_by_subtitle_prefix(lib):
    lib.note("茶馆：成都的公共生活与微观世界", "# 茶馆\n\n想法\n", title="茶馆：成都的公共生活与微观世界", author=None)
    lib.lists["read"] = [douban("A", "茶馆", "王笛")]
    [book] = lib.catalog()
    assert book["key"] == "db:A"
    assert book["note"] == "Reading/Books/茶馆：成都的公共生活与微观世界.md"
    assert book["text"] == "# 茶馆\n\n想法\n"


def test_note_matches_by_douban_alias(lib):
    lib.note("老版茶馆", title="老版茶馆", douban_id='"B"')
    lib.lists["read"] = [douban("A", "茶馆", "王笛")]
    lib.lists["wish"] = [douban("B", "茶馆", "王笛")]
    [book] = lib.catalog()
    assert (book["key"], book["note"]) == ("db:A", "Reading/Books/老版茶馆.md")


def test_ambiguous_note_stands_alone(lib):
    lib.note("自我", title="自我", author=None)
    lib.lists["wish"] = [douban("A", "自我", "甲"), douban("B", "自我", "乙")]
    catalog = lib.catalog()
    assert [b["key"] for b in catalog] == ["note:自我", "db:A", "db:B"]
    assert [b["note"] for b in catalog[1:]] == [None, None]


def test_a_note_with_no_match_is_listed(lib):
    lib.note("没有出处的书", "正文")
    [book] = lib.catalog()
    assert (book["key"], book["title"], book["source"], book["author"]) == ("note:没有出处的书", "没有出处的书", "笔记", None)


def test_order_notes_first_then_sources_by_date(lib):
    old = lib.note("旧笔记", title="旧笔记")
    lib.note("新笔记", title="新笔记")
    os.utime(old, (1, 1))
    lib.lists["read"] = [douban("R", "读过的书")]
    lib.lists["wish"] = [douban("W1", "早想读", wish_date="2026-01-01"), douban("W2", "晚想读", wish_date="2026-09-01")]
    lib.lists["weread"] = [weread("X1", "早读", last=1), weread("X2", "晚读", last=9)]
    assert titles(lib.catalog()) == ["新笔记", "旧笔记", "读过的书", "晚想读", "早想读", "晚读", "早读"]


def test_cached_cover_is_reported(lib):
    lib.lists["read"] = [douban("A", "有封面"), douban("B", "没封面")]
    (lib.cache / "covers").mkdir(parents=True)
    (lib.cache / "covers" / "db_A.jpg").write_bytes(b"jpg")
    a, b = lib.catalog()
    assert a["cover"] == str(lib.cache / "covers" / "db_A.jpg")
    assert b["cover"] is None


def test_broken_source_is_skipped(lib, capsys):
    lib.note("一篇笔记", title="一篇笔记")
    lib.lists["weread"] = [weread("W1", "微信里的书")]
    lib.write_lists()
    (lib.vault / "data" / "read.json").write_text("{not json")
    (lib.vault / "data" / "wish.json").unlink()
    assert titles(lib.catalog(write=False)) == ["一篇笔记", "微信里的书"]
    assert "read.json" in capsys.readouterr().err


def test_weread_title_with_an_edition_note_merges(lib):
    lib.lists["read"] = [douban("K", "卡拉马佐夫兄弟", "陀思妥耶夫斯基")]
    lib.lists["weread"] = [weread("W1", "卡拉马佐夫兄弟（果麦经典）"), weread("W2", "Bloodline (Cradle Book 9) (Z-Library)")]
    assert [b["key"] for b in lib.catalog()] == ["db:K", "wr:W2"]


def test_volumes_of_a_series_stay_apart(lib):
    lib.lists["weread"] = [weread("W1", "Bloodline (Cradle Book 9)", last=2), weread("W2", "Bloodline (Cradle Book 8)", last=1)]
    assert [b["key"] for b in lib.catalog()] == ["wr:W1", "wr:W2"]


# ---- a book's note ----
from datetime import date

from books import cover_rel_for, note_rel_for, render_book_template, safe_name


def book(title, author=None, id=None, aliases=(), note=None):
    return {"key": f"db:{id}" if id else "wr:x", "title": title, "author": author, "doubanId": id,
            "aliases": list(aliases), "note": note, "cover": None}


def test_note_name_is_filesystem_safe():
    assert safe_name('A/B: C?') == 'A／B： C？'
    assert safe_name('.hidden') == 'hidden'
    assert safe_name('《》') == '未命名'


def test_existing_note_is_kept(lib):
    cfg = BooksConfig(folder=lib.folder)
    assert note_rel_for(book("茶馆", note="Reading/Books/茶馆：成都.md"), cfg, lib.vault) == "Reading/Books/茶馆：成都.md"


def test_new_note_goes_in_the_book_folder(lib):
    cfg = BooksConfig(folder=lib.folder)
    assert note_rel_for(book("《人月神话》"), cfg, lib.vault) == "Reading/Books/人月神话.md"


def test_new_note_path_avoids_another_books_file(lib):
    lib.note("茶馆", title="茶馆", douban_id='"X"')
    cfg = BooksConfig(folder=lib.folder)
    assert note_rel_for(book("茶馆", "[中] 老舍", "Y"), cfg, lib.vault) == "Reading/Books/茶馆 (老舍).md"
    assert note_rel_for(book("茶馆", "王笛", "Z", aliases=["X"]), cfg, lib.vault) == "Reading/Books/茶馆.md"


def test_cover_goes_beside_the_note(lib):
    cfg = BooksConfig(folder=lib.folder)
    assert cover_rel_for(cfg, lib.vault, "Reading/Books/人月神话.md") == "Reading/Books/封面/人月神话.jpg"


def test_default_template_renders_yaml_values(lib):
    cfg = BooksConfig(folder=lib.folder)
    bare = render_book_template(cfg, book("无名书"), None, date(2026, 10, 26))
    assert "author: null\ncover: null\ndouban_id: null\ndouban_url: null\ncreated: 2026-10-26\n" in bare
    assert bare.startswith("---\ntitle: 无名书\n")
    assert bare.rstrip("\n").endswith("# 无名书\n\n## 边读边想")
    full = render_book_template(cfg, book("人月神话", "布鲁克斯", "1102259"), "Reading/Books/封面/人月神话.jpg", date(2026, 10, 26))
    assert 'cover: "[[Reading/Books/封面/人月神话.jpg]]"' in full
    assert 'douban_id: "1102259"\ndouban_url: https://book.douban.com/subject/1102259/\n' in full
    assert "author: 布鲁克斯\n" in full


def test_custom_template_is_used(lib):
    tpl = lib.vault / "Book.md"
    tpl.write_text("---\ntype: book-moc\nupdated: {{date}}\n---\n# {{title}}\n\n## {{section}}\n", encoding="utf-8")
    cfg = BooksConfig(folder=lib.folder, template=tpl, section="想法")
    assert render_book_template(cfg, book("人月神话"), None, date(2026, 10, 26)) == \
        "---\ntype: book-moc\nupdated: 2026-10-26\n---\n# 人月神话\n\n## 想法\n"


# ---- covers and Douban search (no network: books.fetch is replaced) ----
import urllib.error

import books as books_mod
from books import SearchError, cover_urls, douban_search, download_covers

SUGGEST = json.dumps([
    {"title": "人月神话", "url": "https://book.douban.com/subject/1102259/", "pic": "https://img9.doubanio.com/view/subject/s/public/s1086045.jpg",
     "author_name": "[美] 弗雷德里克·布鲁克斯", "year": "2002", "type": "b", "id": "1102259"},
    {"title": "人月神话", "url": "https://movie.douban.com/subject/9/", "pic": "", "type": "m", "id": "9"},
]).encode()


def test_cover_urls_try_large_first():
    assert cover_urls("https://img9.doubanio.com/view/subject/s/public/s1.jpg") == [
        "https://img9.doubanio.com/view/subject/l/public/s1.jpg",
        "https://img9.doubanio.com/view/subject/m/public/s1.jpg",
        "https://img9.doubanio.com/view/subject/s/public/s1.jpg"]
    assert cover_urls("https://res.weread.qq.com/x") == ["https://res.weread.qq.com/x"]


def test_download_covers_saves_and_reuses(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(books_mod, "fetch", lambda url, timeout: calls.append(url) or b"jpg")
    items = [{"key": "db:1", "url": "https://img9.doubanio.com/view/subject/s/public/s1.jpg"}]
    first = download_covers(items, tmp_path)
    assert first == {"db:1": str(tmp_path / "covers" / "db_1.jpg")}
    assert (tmp_path / "covers" / "db_1.jpg").read_bytes() == b"jpg"
    assert download_covers(items, tmp_path) == first
    assert len(calls) == 1


def test_cover_download_failure_returns_none(tmp_path, monkeypatch):
    def down(url, timeout):
        raise OSError("offline")
    monkeypatch.setattr(books_mod, "fetch", down)
    assert download_covers([{"key": "db:1", "url": "https://img9.doubanio.com/view/subject/s/public/s1.jpg"}], tmp_path) == {"db:1": None}
    assert list((tmp_path / "covers").glob("*")) == []


def test_douban_search_maps_results(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(books_mod, "fetch", lambda url, timeout: seen.update(url=url, timeout=timeout) or SUGGEST)
    assert douban_search("人月 神话", tmp_path) == [{
        "key": "db:1102259", "title": "人月神话", "author": "[美] 弗雷德里克·布鲁克斯", "doubanId": "1102259", "aliases": [],
        "coverUrl": "https://img9.doubanio.com/view/subject/s/public/s1086045.jpg", "cover": None,
        "source": "豆瓣搜索", "note": None, "text": ""}]
    assert seen == {"url": "https://book.douban.com/j/subject_suggest?q=%E4%BA%BA%E6%9C%88+%E7%A5%9E%E8%AF%9D", "timeout": 5}


def test_douban_search_failure_is_reported(tmp_path, monkeypatch):
    def down(url, timeout):
        raise urllib.error.URLError("offline")
    monkeypatch.setattr(books_mod, "fetch", down)
    with pytest.raises(SearchError):
        douban_search("人月神话", tmp_path)


def test_frontmatter_values_are_yaml_safe(lib):
    cfg = BooksConfig(folder=lib.folder)
    text = render_book_template(cfg, book("Designing Data: The Big Ideas", "[美] 某人 / 译者"), None, date(2026, 10, 26))
    assert 'title: "Designing Data: The Big Ideas"\n' in text
    assert 'author: "[美] 某人 / 译者"\n' in text
    assert "# Designing Data: The Big Ideas\n" in text
    plain = render_book_template(cfg, book("人月神话", "王笛"), None, date(2026, 10, 26))
    assert "title: 人月神话\nauthor: 王笛\n" in plain
