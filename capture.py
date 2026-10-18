"""Append a markdown entry to the end of today's daily note.

Usage: python capture.py "text"   (or pipe text on stdin)
       python capture.py --ensure   (create today's note if missing, print its vault path)
       python capture.py --get [YYYY-MM-DD]             -> {"date", "body"}: the whole note (creates nothing)
       python capture.py --set YYYY-MM-DD BASE BODY     write the whole note; exit 3 if it no longer equals BASE
       python capture.py --attach NAME [EXT] < base64   save a pasted/dropped file where Obsidian puts attachments
       python capture.py --index OUT.json               write note names, file paths and tags for the panel
       python capture.py --doctor                       show which vault, folder, template and format are used

Where the notes are comes from settings.py: the Obsidian vault and its Daily notes settings.
"""
import base64
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

from settings import SetupError
from settings import load as load_settings
from vault import attachment_folder, pasted_image_name, save_attachment, vault_index

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


def _whole_note(settings, day):
    """The panel edits a day's whole note; a missing one shows as the template until saved."""
    path = settings.note_path(date.fromisoformat(day))
    return path.read_text(encoding="utf-8") if path.exists() else settings.template_text(date.fromisoformat(day))


def _doctor(settings):
    template = settings.template
    print(f"vault:    {settings.vault}")
    print(f"日报文件夹: {settings.diary}")
    print(f"模板:     {template or '（无）'}{'' if not template or template.is_file() else '  ⚠️ 文件不存在，新日报会是空白'}")
    print(f"日期格式:  {settings.format}")
    print(f"今天的日报: {settings.note_path(date.today())}")


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
        target = Path(args[1])
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps({**vault_index(vault), "vaultName": vault.name}, ensure_ascii=False), encoding="utf-8")
        tmp.replace(target)
        return
    if args[:1] == ["--get"]:
        day = args[1] if len(args) > 1 else date.today().isoformat()
        _emit(day, _whole_note(settings, day))  # looking never creates a note; the first save does
        return
    if args[:1] == ["--set"]:
        day, base, body = args[1:4]
        current = _whole_note(settings, day)
        if current != base:
            _emit(day, current)
            sys.exit(3)
        path = settings.note_path(date.fromisoformat(day))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
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
