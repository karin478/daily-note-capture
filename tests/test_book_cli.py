import json
from pathlib import Path

import pytest

JPEG = b"\xff\xd8\xffjpg"  # what a downloaded cover starts with

import capture
from settings import BookSource, BooksConfig, Settings


@pytest.fixture
def books(tmp_path, monkeypatch):
    """A vault with book mode on: notes in Reading/Books, one Douban list and one WeRead list."""
    diary = tmp_path / "Diary"
    diary.mkdir()
    folder = tmp_path / "Reading" / "Books"
    folder.mkdir(parents=True)
    cfg = BooksConfig(folder=folder, sources=[BookSource(tmp_path / "data/read.json", "douban", "读过"),
                                              BookSource(tmp_path / "data/weread.json", "weread", "微信读书")])
    s = Settings(vault=tmp_path, diary=diary, template=None, format="YYYY-MM-DD", books=cfg)
    monkeypatch.setattr(capture, "load_settings", lambda: s)
    return s


def run_main(monkeypatch, *args):
    monkeypatch.setattr("sys.argv", ["capture.py", *args])
    capture.main()


def test_doctor_prints_book_mode(books, monkeypatch, capsys):
    run_main(monkeypatch, "--doctor")
    out = capsys.readouterr().out
    assert "书籍文件夹" in out and str(books.books.folder) in out
    assert "书目来源: 2 个（读过、微信读书）" in out
    assert "豆瓣搜索: 开" in out


def test_books_command_writes_catalog(books, tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    (data / "read.json").write_text(json.dumps([{"douban_id": "1", "title": "人月神话", "author": "布鲁克斯"}]))
    out = tmp_path / "cache" / "books.json"
    run_main(monkeypatch, "--books", str(out))
    written = json.loads(out.read_text())
    assert [b["key"] for b in written["books"]] == ["db:1"]
    assert (written["section"], written["doubanSearch"]) == ("边读边想", True)
    assert not out.with_suffix(".tmp").exists()


def test_books_command_without_config_exits_2(books, tmp_path, monkeypatch, capsys):
    books.books = None
    with pytest.raises(SystemExit) as exc:
        run_main(monkeypatch, "--books", str(tmp_path / "books.json"))
    assert exc.value.code == 2
    assert "没有配置书模式" in capsys.readouterr().err


# ---- opening and saving a book's note ----
import io


def open_book(monkeypatch, capsys, book):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(book, ensure_ascii=False)))
    run_main(monkeypatch, "--book-open")
    return json.loads(capsys.readouterr().out)


def files(root):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def test_book_open_new_book_writes_nothing(books, tmp_path, monkeypatch, capsys):
    cover = tmp_path / "cache" / "covers" / "db_1.jpg"
    cover.parent.mkdir(parents=True)
    cover.write_bytes(b"jpg")
    before = files(tmp_path)
    got = open_book(monkeypatch, capsys, {"key": "db:1", "title": "人月神话", "author": None, "doubanId": "1",
                                          "aliases": [], "note": None, "cover": str(cover)})
    assert files(tmp_path) == before
    assert got["date"] == "book:Reading/Books/人月神话.md"
    assert got["exists"] is False
    assert got["body"].startswith("---\ntitle: 人月神话\n")
    assert 'cover: "[[Reading/Books/封面/人月神话.jpg]]"' in got["body"]
    assert (got["coverSrc"], got["coverRel"]) == (str(cover), "Reading/Books/封面/人月神话.jpg")


def test_book_open_existing_note_returns_file(books, monkeypatch, capsys):
    note = books.books.folder / "茶馆.md"
    note.write_text("# 茶馆\n", encoding="utf-8")
    got = open_book(monkeypatch, capsys, {"key": "db:1", "title": "茶馆", "author": None, "doubanId": "1",
                                          "aliases": [], "note": "Reading/Books/茶馆.md", "cover": None})
    assert got == {"key": "db:1", "date": "book:Reading/Books/茶馆.md", "body": "# 茶馆\n", "exists": True,
                   "coverRel": None, "coverSrc": None}


def test_get_book_note(books, monkeypatch, capsys):
    (books.books.folder / "茶馆.md").write_text("# 茶馆\n", encoding="utf-8")
    run_main(monkeypatch, "--get", "book:Reading/Books/茶馆.md")
    assert json.loads(capsys.readouterr().out) == {"date": "book:Reading/Books/茶馆.md", "body": "# 茶馆\n"}
    run_main(monkeypatch, "--get", "book:Reading/Books/没有.md")
    assert json.loads(capsys.readouterr().out)["body"] == ""


def test_set_creates_book_note_and_copies_cover(books, tmp_path, monkeypatch):
    cover = tmp_path / "cache" / "covers" / "db_1.jpg"
    cover.parent.mkdir(parents=True)
    cover.write_bytes(b"jpg")
    body = '---\ncover: "[[Reading/Books/封面/新书.jpg]]"\n---\n# 新书\n'
    run_main(monkeypatch, "--set", "book:Reading/Books/新书.md", body, body + "想法\n", str(cover), "Reading/Books/封面/新书.jpg")
    assert (books.books.folder / "新书.md").read_text() == body + "想法\n"
    assert (books.books.folder / "封面" / "新书.jpg").read_bytes() == b"jpg"


def test_set_book_note_conflict_exits_3(books, monkeypatch):
    note = books.books.folder / "茶馆.md"
    note.write_text("别处改过\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        run_main(monkeypatch, "--set", "book:Reading/Books/茶馆.md", "原来的\n", "原来的\n新的\n")
    assert exc.value.code == 3
    assert note.read_text() == "别处改过\n"


def test_book_key_outside_folder_is_rejected(books, tmp_path, monkeypatch):
    for key in ("book:../x.md", "book:Reading/Books/../../x.md", "book:Diary/x.md", "book:Reading/Books/x.txt"):
        with pytest.raises(SystemExit) as exc:
            run_main(monkeypatch, "--set", key, "a", "b")
        assert exc.value.code == 2
    assert not (tmp_path.parent / "x.md").exists() and not (tmp_path / "x.md").exists()
    assert not (tmp_path / "Diary" / "x.md").exists()


def test_set_existing_book_note_copies_the_cover_it_now_points_at(books, tmp_path, monkeypatch):
    note = books.books.folder / "茶馆.md"
    note.write_text("---\ncover: null\n---\n", encoding="utf-8")
    cover = tmp_path / "db_1.jpg"
    cover.write_bytes(b"jpg")
    body = '---\ncover: "[[Reading/Books/封面/茶馆.jpg]]"\n---\n想法\n'
    run_main(monkeypatch, "--set", "book:Reading/Books/茶馆.md", "---\ncover: null\n---\n", body, str(cover), "Reading/Books/封面/茶馆.jpg")
    assert note.read_text() == body
    assert (books.books.folder / "封面" / "茶馆.jpg").read_bytes() == b"jpg"


# ---- covers and Douban search ----
import books as books_mod


def test_covers_command_writes_paths(books, tmp_path, monkeypatch):
    monkeypatch.setattr(books_mod, "fetch", lambda url, timeout: JPEG)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps([{"key": "wr:1", "url": "https://res.weread.qq.com/1"}])))
    out = tmp_path / "cache" / "covers-1.json"
    run_main(monkeypatch, "--covers", str(out))
    assert json.loads(out.read_text()) == {"wr:1": str(tmp_path / "cache" / "covers" / "wr_1.jpg")}


def test_douban_search_command_reports_failure(books, monkeypatch, capsys):
    def down(url, timeout):
        raise OSError("offline")
    monkeypatch.setattr(books_mod, "fetch", down)
    run_main(monkeypatch, "--douban-search", "人月神话")
    assert json.loads(capsys.readouterr().out) == {"q": "人月神话", "error": True}


def test_book_open_fetches_a_missing_cover(books, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(capture, "CACHE", tmp_path / "cache")
    seen = []
    monkeypatch.setattr(books_mod, "fetch", lambda url, timeout: seen.append(timeout) or JPEG)
    got = open_book(monkeypatch, capsys, {"key": "db:7", "title": "新书", "doubanId": "7", "aliases": [], "note": None,
                                          "cover": None, "coverUrl": "https://img1.doubanio.com/view/subject/s/public/s7.jpg"})
    assert got["coverSrc"] == str(tmp_path / "cache" / "covers" / "db_7.jpg")
    assert 'cover: "[[Reading/Books/封面/新书.jpg]]"' in got["body"]
    assert seen == [3]


def test_book_open_without_network_still_opens(books, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(capture, "CACHE", tmp_path / "cache")
    def down(url, timeout):
        raise OSError("offline")
    monkeypatch.setattr(books_mod, "fetch", down)
    got = open_book(monkeypatch, capsys, {"key": "db:7", "title": "新书", "doubanId": "7", "aliases": [], "note": None,
                                          "cover": None, "coverUrl": "https://img1.doubanio.com/view/subject/s/public/s7.jpg"})
    assert (got["coverSrc"], got["exists"]) == (None, False)
    assert "cover: null" in got["body"]


def test_book_open_says_which_book_it_answers(books, monkeypatch, capsys):
    got = open_book(monkeypatch, capsys, {"key": "db:1", "title": "茶馆", "doubanId": "1", "aliases": [], "note": None, "cover": None})
    assert got["key"] == "db:1"
