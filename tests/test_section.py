import base64
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

import capture
from settings import SetupError, Settings

TEMPLATE = "- [ ] \n- [ ] \n- [ ] \n\n- \n- \n- \n"


@pytest.fixture
def vault(tmp_path, monkeypatch):
    diary = tmp_path / "Diary"
    diary.mkdir()
    tpl = tmp_path / "tpl.md"
    tpl.write_text(TEMPLATE)
    s = Settings(vault=tmp_path, diary=diary, template=tpl, format="YYYY-MM-DD")
    monkeypatch.setattr(capture, "load_settings", lambda: s)
    return diary


def run_main(monkeypatch, *args):
    monkeypatch.setattr("sys.argv", ["capture.py", *args])
    capture.main()


def test_get_shows_a_missing_note_as_the_template_without_creating_it(vault, monkeypatch, capsys):
    run_main(monkeypatch, "--get", "2026-10-17")
    assert not (vault / "2026-10-17.md").exists()
    assert json.loads(capsys.readouterr().out) == {"date": "2026-10-17", "body": TEMPLATE}


def test_get_returns_the_whole_note(vault, monkeypatch, capsys):
    (vault / "2026-10-17.md").write_text("# 方向\n\n- a\n\n# Note\n\nb\n")
    run_main(monkeypatch, "--get", "2026-10-17")
    assert json.loads(capsys.readouterr().out)["body"] == "# 方向\n\n- a\n\n# Note\n\nb\n"


def test_set_creates_a_missing_note_when_it_was_shown_as_the_template(vault, monkeypatch, capsys):
    run_main(monkeypatch, "--set", "2026-10-17", TEMPLATE, "- [ ] x\n")
    assert (vault / "2026-10-17.md").read_text() == "- [ ] x\n"


def test_set_writes_the_whole_note_verbatim(vault, monkeypatch, capsys):
    p = vault / "2026-10-17.md"
    p.write_text("old\n")
    body = "\n\n# 方向\n- a \n\n# 阅读\n- b  "
    run_main(monkeypatch, "--set", "2026-10-17", "old\n", body)
    assert p.read_text() == body
    assert json.loads(capsys.readouterr().out) == {"date": "2026-10-17", "body": body}


def test_set_refuses_when_note_changed_elsewhere(vault, monkeypatch, capsys):
    p = vault / "2026-10-17.md"
    p.write_text("edited in obsidian\n")
    with pytest.raises(SystemExit) as exc:
        run_main(monkeypatch, "--set", "2026-10-17", "old\n", "new")
    assert exc.value.code == 3
    assert p.read_text() == "edited in obsidian\n"
    assert json.loads(capsys.readouterr().out) == {"date": "2026-10-17", "body": "edited in obsidian\n"}


def test_attach_saves_stdin_base64_next_to_the_vault(vault, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(base64.b64encode(b"%PDF").decode()))
    run_main(monkeypatch, "--attach", "报告.pdf")
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "报告.pdf"
    assert (vault.parent / "报告.pdf").read_bytes() == b"%PDF"


def test_attach_without_a_name_uses_obsidians_pasted_image_name(vault, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(base64.b64encode(b"\x89PNG").decode()))
    run_main(monkeypatch, "--attach", "", "png")
    name = json.loads(capsys.readouterr().out)["name"]
    assert name.startswith("Pasted image ") and name.endswith(".png")


def test_index_writes_the_vault_index_to_a_file(vault, monkeypatch, tmp_path):
    # A file, not stdout: the index is hundreds of KB, more than Hammerspoon's pipes carry intact.
    (vault / "2026-10-17.md").write_text("#tag\n")
    target = tmp_path / "cache" / "index.json"
    run_main(monkeypatch, "--index", str(target))
    out = json.loads(target.read_text())
    assert out["tags"] == ["tag"] and {"name": "2026-10-17", "folder": "Diary"} in out["notes"]
    assert out["vaultName"] == vault.parent.name


def test_get_and_set_follow_the_date_format_and_fill_the_template(vault, monkeypatch, capsys):
    s = capture.load_settings()
    s.format = "YYYY/MM/DD"
    s.template.write_text("# {{date}}\n")
    run_main(monkeypatch, "--get", "2026-10-17")
    assert json.loads(capsys.readouterr().out) == {"date": "2026-10-17", "body": "# 2026-10-17\n"}
    run_main(monkeypatch, "--set", "2026-10-17", "# 2026-10-17\n", "# 2026-10-17\n- a\n")
    assert (vault / "2026/10/17.md").read_text() == "# 2026-10-17\n- a\n"


def test_doctor_prints_where_notes_go(vault, monkeypatch, capsys):
    run_main(monkeypatch, "--doctor")
    out = capsys.readouterr().out
    assert str(vault) in out and "tpl.md" in out and "YYYY-MM-DD" in out


def test_a_setup_problem_exits_2_with_the_reason_on_stderr(monkeypatch, capsys):
    def broken():
        raise SetupError("找不到 Obsidian vault")
    monkeypatch.setattr(capture, "load_settings", broken)
    with pytest.raises(SystemExit) as exc:
        run_main(monkeypatch, "--get", "2026-10-17")
    assert exc.value.code == 2
    assert "找不到 Obsidian vault" in capsys.readouterr().err
