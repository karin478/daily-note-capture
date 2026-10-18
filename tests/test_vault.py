import json
from datetime import datetime

import pytest

from vault import attachment_folder, pasted_image_name, save_attachment, vault_index


@pytest.fixture
def vault(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Journal" / "Daily").mkdir(parents=True)
    return tmp_path


def config(vault, **settings):
    (vault / ".obsidian" / "app.json").write_text(json.dumps(settings))


def test_attachments_default_to_the_vault_root(vault):
    assert attachment_folder(vault, vault / "Journal/Daily") == vault


def test_attachments_follow_a_configured_folder(vault):
    config(vault, attachmentFolderPath="附件/图片")
    assert attachment_folder(vault, vault / "Journal/Daily") == vault / "附件/图片"


def test_attachments_slash_means_vault_root(vault):
    config(vault, attachmentFolderPath="/")
    assert attachment_folder(vault, vault / "Journal/Daily") == vault


def test_attachments_dot_path_is_relative_to_the_note(vault):
    config(vault, attachmentFolderPath="./assets")
    assert attachment_folder(vault, vault / "Journal/Daily") == vault / "Journal/Daily/assets"


def test_pasted_image_name_matches_obsidian():
    assert pasted_image_name(datetime(2026, 10, 17, 16, 30, 5), "png") == "Pasted image 20261017163005.png"


def test_save_attachment_writes_bytes_and_returns_name_and_path(tmp_path):
    out = save_attachment(tmp_path / "att", "图.png", b"\x89PNG")
    assert out == {"name": "图.png", "path": str(tmp_path / "att" / "图.png")}
    assert (tmp_path / "att" / "图.png").read_bytes() == b"\x89PNG"


def test_save_attachment_never_overwrites(tmp_path):
    save_attachment(tmp_path, "a.pdf", b"1")
    assert save_attachment(tmp_path, "a.pdf", b"2")["name"] == "a 1.pdf"
    assert save_attachment(tmp_path, "a.pdf", b"3")["name"] == "a 2.pdf"
    assert (tmp_path / "a.pdf").read_bytes() == b"1"


def test_save_attachment_strips_directories_from_the_name(tmp_path):
    assert save_attachment(tmp_path, "../../evil.txt", b"x")["name"] == "evil.txt"
    assert (tmp_path / "evil.txt").exists()


def test_index_lists_notes_files_and_tags(vault):
    (vault / "Journal/Daily/2026-10-17.md").write_text("今天 #工作 和 #life/health\n")
    (vault / "想法.md").write_text("---\ntags:\n  - 读书\n---\n# 标题\n正文 #想法\n")
    (vault / "Pasted image 1.png").write_bytes(b"")
    (vault / ".obsidian" / "hidden.md").write_text("#nope")
    idx = vault_index(vault)
    assert idx["vault"] == str(vault)
    assert sorted(n["name"] for n in idx["notes"]) == ["2026-10-17", "想法"]
    assert idx["files"]["Pasted image 1.png"] == str(vault / "Pasted image 1.png")
    assert idx["files"]["想法.md"] == str(vault / "想法.md")
    assert idx["tags"] == sorted(["工作", "life/health", "读书", "想法"])


def test_index_ignores_headings_code_and_url_fragments(vault):
    (vault / "a.md").write_text("# 标题\n## 二级\n`#code` https://x.y/#frag\n```\n#infence\n```\n#real\n")
    assert vault_index(vault)["tags"] == ["real"]


def test_index_notes_carry_their_folder(vault):
    (vault / "Journal/Daily/2026-10-17.md").write_text("")
    note = vault_index(vault)["notes"][0]
    assert note == {"name": "2026-10-17", "folder": "Journal/Daily"}
