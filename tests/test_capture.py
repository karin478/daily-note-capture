from datetime import date

import pytest

import capture
from capture import append_note
from settings import Settings

TEMPLATE = "- [ ] \n- [ ] \n- [ ] \n\n- \n- \n- \n"
PUSH = "---\n\n## 📥 Agent Push\n\ndraft\n"


@pytest.fixture
def diary(tmp_path):
    d = tmp_path / "Diary"
    d.mkdir()
    return d


def test_creates_missing_note_from_template(diary):
    p = diary / "2026-10-17.md"
    append_note(p, "hello", TEMPLATE)
    assert p.read_text() == TEMPLATE + "\nhello\n"


def test_appends_to_the_end_of_the_note(diary):
    p = diary / "2026-10-17.md"
    p.write_text(TEMPLATE)
    append_note(p, "first", TEMPLATE)
    append_note(p, "second", TEMPLATE)
    assert p.read_text() == TEMPLATE + "\nfirst\n\nsecond\n"


def test_keeps_markdown_verbatim(diary):
    p = diary / "2026-10-17.md"
    p.write_text(TEMPLATE)
    entry = "**粗体** [[双链]]\n- a\n\t- b\n\n```py\nx = 1\n```"
    append_note(p, entry, TEMPLATE)
    assert p.read_text() == TEMPLATE + "\n" + entry + "\n"


def test_strips_surrounding_blank_lines(diary):
    p = diary / "2026-10-17.md"
    p.write_text(TEMPLATE)
    append_note(p, "\n\n  hi  \n\n", TEMPLATE)
    assert p.read_text() == TEMPLATE + "\n  hi\n"


def test_empty_entry_is_ignored(diary):
    p = diary / "2026-10-17.md"
    append_note(p, "  \n\n", TEMPLATE)
    assert not p.exists()


def test_never_adds_a_heading(diary):
    p = diary / "2026-10-17.md"
    p.write_text("# 现在\n- [ ] x\n")
    append_note(p, "hi", TEMPLATE)
    assert p.read_text() == "# 现在\n- [ ] x\n\nhi\n"


def test_inserts_before_agent_push_block(diary):
    p = diary / "2026-10-17.md"
    p.write_text("old\n\n" + PUSH)
    append_note(p, "new", TEMPLATE)
    assert p.read_text() == "old\n\nnew\n\n" + PUSH


@pytest.fixture
def cfg(diary, tmp_path, monkeypatch):
    tpl = tmp_path / "tpl.md"
    tpl.write_text(TEMPLATE)
    s = Settings(vault=tmp_path, diary=diary, template=tpl, format="YYYY-MM-DD")
    monkeypatch.setattr(capture, "load_settings", lambda: s)
    return s


def test_main_reads_entry_from_argv_into_todays_note(cfg, monkeypatch):
    monkeypatch.setattr("sys.argv", ["capture.py", "from argv"])
    capture.main()
    assert cfg.note_path(date.today()).read_text() == TEMPLATE + "\nfrom argv\n"


def test_ensure_note_creates_from_template(diary):
    p = diary / "2026-10-17.md"
    capture.ensure_note(p, TEMPLATE)
    assert p.read_text() == TEMPLATE


def test_ensure_note_leaves_existing_note_alone(diary):
    p = diary / "2026-10-17.md"
    p.write_text("mine")
    capture.ensure_note(p, TEMPLATE)
    assert p.read_text() == "mine"


def test_main_ensure_flag_prints_vault_relative_path(cfg, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["capture.py", "--ensure"])
    capture.main()
    today = cfg.note_path(date.today())
    assert today.read_text() == TEMPLATE
    assert capsys.readouterr().out == f"Diary/{date.today().isoformat()}.md\n"
