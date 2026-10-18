"""Vault-wide helpers for the note panel: where attachments go, and what can be linked."""
import json
import re
from pathlib import Path

# Obsidian tags: letters, digits, _, -, / with at least one non-digit.
TAG = re.compile(r"(?<![\w/#&])#([\w\-/]*[^\W\d_][\w\-/]*)")
FENCE = re.compile(r"^(```|~~~).*?^\1", re.M | re.S)
INLINE_CODE = re.compile(r"`[^`\n]*`")
URL = re.compile(r"https?://\S+")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---", re.S)
FM_TAGS = re.compile(r"^tags:[ \t]*(.*)$((?:\n[ \t]+-[ \t]*.+)*)", re.M)


def _hidden(path, root):
    return any(part.startswith(".") for part in path.relative_to(root).parts)


def attachment_folder(vault, note_dir):
    """Obsidian's "Default location for new attachments" (app.json attachmentFolderPath)."""
    vault, note_dir = Path(vault), Path(note_dir)
    try:
        setting = json.loads((vault / ".obsidian" / "app.json").read_text(encoding="utf-8")).get("attachmentFolderPath")
    except (OSError, ValueError):
        setting = None
    if not setting or setting == "/":
        return vault
    if setting == "./" or setting.startswith("./"):
        return note_dir / setting[2:]
    return vault / setting


def pasted_image_name(now, ext):
    return f"Pasted image {now:%Y%m%d%H%M%S}.{ext}"


def save_attachment(folder, name, data):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    name = Path(name).name
    stem, suffix = Path(name).stem, Path(name).suffix
    target, n = folder / name, 0
    while target.exists():
        n += 1
        target = folder / f"{stem} {n}{suffix}"
    target.write_bytes(data)
    return {"name": target.name, "path": str(target)}


def _tags(text):
    tags = set()
    fm = FRONTMATTER.match(text)
    if fm:
        for m in FM_TAGS.finditer(fm.group(1)):
            inline, items = m.group(1), m.group(2)
            values = re.findall(r"-\s*(.+)", items) if items else re.split(r"[,\s]+", inline.strip("[] "))
            tags.update(v.strip().strip("'\"#") for v in values if v.strip())
        text = text[fm.end():]
    text = INLINE_CODE.sub("", FENCE.sub("", text))
    text = URL.sub("", text)
    tags.update(TAG.findall(text))
    return tags


def vault_index(vault):
    vault = Path(vault)
    notes, files, tags = [], {}, set()
    for path in vault.rglob("*"):
        if not path.is_file() or _hidden(path, vault):
            continue
        files.setdefault(path.name, str(path))
        if path.suffix == ".md":
            folder = path.parent.relative_to(vault).as_posix()
            notes.append({"name": path.stem, "folder": "" if folder == "." else folder})
            try:
                tags |= _tags(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                pass
    return {"vault": str(vault), "notes": notes, "files": files, "tags": sorted(tags)}
