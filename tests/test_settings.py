import json
from datetime import date
from pathlib import Path

import pytest

from settings import SetupError, format_date, load, render_template


@pytest.fixture
def home(tmp_path):
    """A fake machine: Obsidian's vault list, a config dir, and vaults to point them at."""
    (tmp_path / "obsidian").mkdir()
    (tmp_path / "config").mkdir()
    return tmp_path


def make_vault(root, name, daily=None, periodic=None):
    vault = root / name
    (vault / ".obsidian").mkdir(parents=True)
    if daily is not None:
        (vault / ".obsidian" / "daily-notes.json").write_text(json.dumps(daily))
    if periodic is not None:
        plugin = vault / ".obsidian" / "plugins" / "periodic-notes"
        plugin.mkdir(parents=True)
        (plugin / "data.json").write_text(json.dumps({"daily": periodic}))
    return vault


def register(home, *vaults, open_one=None):
    data = {"vaults": {str(i): {"path": str(v), "ts": 1, **({"open": True} if v == open_one else {})}
                       for i, v in enumerate(vaults)}}
    (home / "obsidian" / "obsidian.json").write_text(json.dumps(data))


def configure(home, **config):
    (home / "config" / "config.json").write_text(json.dumps(config))


def settings(home):
    return load(home / "config" / "config.json", home / "obsidian" / "obsidian.json")


def test_the_only_vault_obsidian_knows_is_used(home):
    vault = make_vault(home, "Notes", daily={"folder": "Journal/Daily", "template": "Templates/Day"})
    register(home, vault)
    s = settings(home)
    assert s.vault == vault
    assert s.diary == vault / "Journal/Daily"
    assert s.template == vault / "Templates/Day.md"
    assert s.format == "YYYY-MM-DD"


def test_daily_notes_without_settings_go_to_the_vault_root_with_no_template(home):
    vault = make_vault(home, "Notes", daily={})
    register(home, vault)
    s = settings(home)
    assert (s.diary, s.template, s.format) == (vault, None, "YYYY-MM-DD")


def test_periodic_notes_is_used_when_core_daily_notes_has_no_settings(home):
    vault = make_vault(home, "Notes", periodic={"enabled": True, "folder": "Days", "template": "T/day.md", "format": "YYYY/MM/DD"})
    register(home, vault)
    s = settings(home)
    assert (s.diary, s.template, s.format) == (vault / "Days", vault / "T/day.md", "YYYY/MM/DD")


def test_several_vaults_without_a_config_is_an_error_naming_them(home):
    a, b = make_vault(home, "Work", daily={}), make_vault(home, "Home", daily={})
    register(home, a, b, open_one=a)
    with pytest.raises(SetupError) as err:
        settings(home)
    assert str(a) in str(err.value) and str(b) in str(err.value)


def test_the_config_picks_the_vault_and_can_override_daily_settings(home):
    a, b = make_vault(home, "Work", daily={"folder": "Daily"}), make_vault(home, "Home", daily={})
    register(home, a, b)
    configure(home, vault=str(a), template="Tpl/day")
    s = settings(home)
    assert (s.vault, s.diary, s.template) == (a, a / "Daily", a / "Tpl/day.md")


def test_a_config_vault_works_even_if_obsidian_has_never_opened_it(home):
    vault = make_vault(home, "Elsewhere", daily={"folder": "D"})
    configure(home, vault=str(vault))
    assert settings(home).diary == vault / "D"


def test_no_vault_anywhere_is_an_error(home):
    with pytest.raises(SetupError):
        settings(home)


def test_a_config_vault_that_does_not_exist_is_an_error(home):
    configure(home, vault=str(home / "missing"))
    with pytest.raises(SetupError):
        settings(home)


def test_note_path_follows_the_date_format(home):
    vault = make_vault(home, "Notes", daily={"folder": "D", "format": "YYYY/MM/[Day] D"})
    register(home, vault)
    assert settings(home).note_path(date(2026, 3, 7)) == vault / "D/2026/03/Day 7.md"


@pytest.mark.parametrize("fmt, want", [
    ("YYYY-MM-DD", "2026-03-07"),
    ("YY.M.D", "26.3.7"),
    ("[Week] YYYY", "Week 2026"),
    ("YYYYMMDD", "20260307"),
])
def test_format_date(fmt, want):
    assert format_date(fmt, date(2026, 3, 7)) == want


@pytest.mark.parametrize("fmt", ["dddd YYYY-MM-DD", "MMMM D", "Do"])
def test_unsupported_date_tokens_are_an_error(fmt):
    with pytest.raises(SetupError):
        format_date(fmt, date(2026, 3, 7))


def test_render_template_fills_date_and_title_and_leaves_the_rest():
    text = "# {{title}}\n{{date}} {{date:YY/M/D}} {{time}} <% tp.date.now() %>\n"
    assert render_template(text, date(2026, 3, 7), "2026-03-07") == \
        "# 2026-03-07\n2026-03-07 26/3/7 {{time}} <% tp.date.now() %>\n"


def test_template_text_for_a_day(home):
    vault = make_vault(home, "Notes", daily={"template": "T"})
    (vault / "T.md").write_text("# {{date}}\n- [ ] \n")
    register(home, vault)
    assert settings(home).template_text(date(2026, 3, 7)) == "# 2026-03-07\n- [ ] \n"


def test_a_missing_template_reads_as_empty(home):
    vault = make_vault(home, "Notes", daily={})
    register(home, vault)
    assert settings(home).template_text(date(2026, 3, 7)) == ""


def test_year_notes_follow_periodic_notes_yearly_settings(home):
    vault = make_vault(home, "Notes", daily={"folder": "D"})
    plugin = vault / ".obsidian/plugins/periodic-notes"
    plugin.mkdir(parents=True)
    (plugin / "data.json").write_text(json.dumps({"yearly": {"enabled": True, "folder": "Years", "template": "T/year", "format": "[Y]YYYY"}}))
    (vault / "T").mkdir()
    (vault / "T/year.md").write_text("# {{date}} {{title}}\n")
    register(home, vault)
    s = settings(home)
    assert s.year_path(2026) == vault / "Years/Y2026.md"
    assert s.year_template_text(2026) == "# Y2026 Y2026\n"


def test_year_notes_sit_beside_the_daily_notes_by_default(home):
    vault = make_vault(home, "Notes", daily={"folder": "D"})
    register(home, vault)
    s = settings(home)
    assert s.year_path(2026) == vault / "D/2026.md"
    assert s.year_template_text(2026) == ""


def test_the_config_can_place_year_notes(home):
    vault = make_vault(home, "Notes", periodic={"enabled": True, "folder": "Days"})
    register(home, vault)
    configure(home, year_folder="Life/Years", year_format="YYYY[ 年报]")
    assert settings(home).year_path(2026) == vault / "Life/Years/2026 年报.md"


# ---- book mode ----

def book_settings(home, books):
    vault = make_vault(home, "Notes", daily={})
    register(home, vault)
    configure(home, books=books)
    return vault, settings(home)


def test_books_absent_means_none(home):
    vault = make_vault(home, "Notes", daily={})
    register(home, vault)
    assert settings(home).books is None


def test_books_paths_resolve_against_vault(home):
    vault, s = book_settings(home, {"folder": "R/书籍",
                                    "sources": [{"path": "data/a.json", "kind": "douban", "label": "读过"}]})
    b = s.books
    assert b.folder == vault / "R/书籍"
    assert b.sources[0].path == vault / "data/a.json"
    assert (b.sources[0].kind, b.sources[0].label) == ("douban", "读过")
    assert (b.section, b.cover_folder, b.douban_search, b.template) == ("边读边想", "封面", True, None)


def test_books_absolute_source_path_kept(home):
    _, s = book_settings(home, {"folder": "R", "sources": [{"path": "/tmp/x.json", "kind": "weread", "label": "微信读书"}]})
    assert s.books.sources[0].path == Path("/tmp/x.json")


def test_books_template_resolves_like_daily_template(home):
    vault, s = book_settings(home, {"folder": "R", "sources": [], "template": "Templates/Book"})
    assert s.books.template == vault / "Templates/Book.md"


def test_books_unknown_kind_is_setup_error(home):
    with pytest.raises(SetupError, match="goodreads"):
        book_settings(home, {"folder": "R", "sources": [{"path": "a.json", "kind": "goodreads", "label": "x"}]})


def test_books_without_folder_is_setup_error(home):
    with pytest.raises(SetupError, match="folder"):
        book_settings(home, {"sources": []})
