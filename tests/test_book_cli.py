import json
from pathlib import Path

import pytest

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
