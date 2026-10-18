"""Where the daily notes live, found the way Obsidian itself would find them.

The vault comes from the config file, or else from Obsidian's own list of vaults when it knows
exactly one. The daily-note folder, template and date format come from the vault's Daily notes
(or Periodic Notes) settings; the config file can override each of them.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

CONFIG = Path.home() / ".config/daily-note-capture/config.json"
OBSIDIAN = Path.home() / "Library/Application Support/obsidian/obsidian.json"
DEFAULT_FORMAT = "YYYY-MM-DD"

TOKEN = re.compile(r"\[([^\]]*)\]|([A-Za-z])\2*|.", re.S)
PLACEHOLDER = re.compile(r"\{\{(date|title)(?::([^}]*))?\}\}")


class SetupError(Exception):
    pass


def format_date(fmt, day):
    """The part of moment.js formatting daily notes need: YYYY YY MM M DD D and [literal]."""
    values = {"YYYY": f"{day.year:04d}", "YY": f"{day.year % 100:02d}", "MM": f"{day.month:02d}",
              "M": str(day.month), "DD": f"{day.day:02d}", "D": str(day.day)}
    out = []
    for m in TOKEN.finditer(fmt):
        literal, letter = m.group(1), m.group(2)
        if literal is not None:
            out.append(literal)
        elif letter:
            if m.group(0) not in values:
                raise SetupError(f"日期格式里的 {m.group(0)} 还不支持（格式：{fmt}），只支持 YYYY YY MM M DD D")
            out.append(values[m.group(0)])
        else:
            out.append(m.group(0))
    return "".join(out)


def render_template(text, day, title):
    """Fill Obsidian's core template placeholders {{date}}, {{date:FORMAT}} and {{title}}."""
    def fill(m):
        try:
            return title if m.group(1) == "title" else format_date(m.group(2) or DEFAULT_FORMAT, day)
        except SetupError:
            return m.group(0)
    return PLACEHOLDER.sub(fill, text)


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _md(vault, name):
    if not name:
        return None
    name = name.strip("/")
    return vault / (name if name.endswith(".md") else name + ".md")


@dataclass
class Settings:
    vault: Path
    diary: Path
    template: Path | None
    format: str
    config: dict = field(default_factory=dict)

    def note_path(self, day):
        return self.diary / (format_date(self.format, day) + ".md")

    def template_text(self, day):
        if not self.template or not self.template.is_file():
            return ""
        title = self.note_path(day).stem
        return render_template(self.template.read_text(encoding="utf-8"), day, title)


def _find_vault(config, obsidian_json):
    if config.get("vault"):
        vault = Path(config["vault"]).expanduser()
        if not vault.is_dir():
            raise SetupError(f"配置里的 vault 不存在：{vault}")
        return vault
    known = (_read_json(obsidian_json) or {}).get("vaults", {})
    paths = [Path(v["path"]) for v in known.values() if v.get("path") and Path(v["path"]).is_dir()]
    if len(paths) == 1:
        return paths[0]
    if not paths:
        raise SetupError(f"找不到 Obsidian vault。请在 {CONFIG} 里写上 {{\"vault\": \"/path/to/vault\"}}")
    listed = "\n".join(f"  {p}" for p in paths)
    raise SetupError(f"Obsidian 里有多个 vault，请在 {CONFIG} 里写上要用哪个，例如 {{\"vault\": \"{paths[0]}\"}}：\n{listed}")


def _daily_settings(vault):
    core = _read_json(vault / ".obsidian/daily-notes.json") or {}
    if any(core.get(k) for k in ("folder", "template", "format")):
        return core
    periodic = (_read_json(vault / ".obsidian/plugins/periodic-notes/data.json") or {}).get("daily") or {}
    if periodic.get("enabled"):
        return periodic
    return core


def load(config_path=CONFIG, obsidian_json=OBSIDIAN):
    config = _read_json(config_path) or {}
    vault = _find_vault(config, obsidian_json)
    daily = {**_daily_settings(vault), **{k: config[k] for k in ("folder", "template", "format") if k in config}}
    folder = (daily.get("folder") or "").strip("/")
    settings = Settings(vault=vault, diary=vault / folder if folder else vault,
                        template=_md(vault, daily.get("template")),
                        format=daily.get("format") or DEFAULT_FORMAT, config=config)
    format_date(settings.format, date.today())  # an unsupported format fails here, not on first save
    return settings
