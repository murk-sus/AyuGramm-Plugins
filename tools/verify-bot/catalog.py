"""Fonts and plugins the team bot publishes to the catalog.

`inspect(filename, data)` checks an uploaded file with the same rules as tools/build_index.py and
tools/build_fonts_index.py and returns an Item; `changes(item, ...)` lists the repository files
to write or delete. The bot commits them in one commit and the Catalog workflow rebuilds
index.json, fonts/index.json and the README from them.
"""
import base64
import hashlib
import json
import re
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_index  # noqa: E402  (same rules as the CI index build)

ID = re.compile(r"^[a-z0-9_-]{1,64}$")
NICK = re.compile(r"^@[A-Za-z0-9_]{4,32}$")
FONT_MAX_BYTES = 15 * 1024 * 1024
PLUGIN_FILES = ("plugin.ayu.js", "plugin.ayu.py", "plugin.ayu.lua", "plugin.wasm", "plugin.iosplug")


class Refused(Exception):
    """The upload cannot go into the catalog; the message is shown to the team member."""


@dataclass
class Item:
    kind: str                 # "font" or a plugin kind: js, python, lua, wasm, iosplug
    id: str
    name: str
    version: str = ""
    description: str = ""
    filename: str = ""        # file name inside the item's folder
    data: bytes = b""
    injects: bool = False
    extra: dict = field(default_factory=dict)

    @property
    def is_font(self):
        return self.kind == "font"

    @property
    def folder(self):
        return f"fonts/{self.id}" if self.is_font else f"plugins/{self.id}"

    @property
    def sha256(self):
        return hashlib.sha256(self.data).hexdigest()


def slug(text):
    value = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return value[:64] or "font"


def font_names(data):
    """Family (1), style (2) and PostScript (6) names from the font's name table."""
    if len(data) < 12 or data[:4] not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
        raise Refused("Это не шрифт .ttf или .otf.")
    try:
        count = struct.unpack(">H", data[4:6])[0]
        names = {}
        for i in range(count):
            tag, _, offset, _ = struct.unpack(">4sIII", data[12 + 16 * i:28 + 16 * i])
            if tag != b"name":
                continue
            _, records, strings = struct.unpack(">HHH", data[offset:offset + 6])
            for r in range(records):
                pid, _, _, nid, length, start = struct.unpack(">HHHHHH", data[offset + 6 + 12 * r:offset + 18 + 12 * r])
                if nid in (1, 2, 6) and nid not in names:
                    raw = data[offset + strings + start:offset + strings + start + length]
                    names[nid] = raw.decode("utf-16-be", "replace") if pid in (0, 3) else raw.decode("latin-1")
    except struct.error:
        raise Refused("Шрифт повреждён: не читается таблица имён.")
    return names


def inspect(filename, data):
    """Checks an upload and describes it. Raises Refused with a reason the bot can show."""
    lower = filename.lower()
    if lower.endswith((".ttf", ".otf")):
        if len(data) > FONT_MAX_BYTES:
            raise Refused("Шрифт больше 15 МБ.")
        names = font_names(data)
        family = (names.get(1) or Path(filename).stem).strip()
        if not names.get(6):
            # iOS registers a font by its PostScript name; without one it cannot be chosen.
            raise Refused("В шрифте нет PostScript-имени (name ID 6): iOS не сможет его выбрать. Попросите автора добавить имя, "
                          "или добавьте его в FontForge / fontTools и пришлите снова.")
        ext = ".otf" if lower.endswith(".otf") else ".ttf"
        return Item(kind="font", id=slug(family), name=family[:64], filename="font" + ext, data=data,
                    extra={"style": names.get(2, ""), "postscript": names.get(6, "")})
    if lower.endswith(".iosplug"):
        kind, target = "iosplug", "plugin.iosplug"
    elif lower.endswith(".wasm"):
        kind, target = "wasm", "plugin.wasm"
    elif lower.endswith(".py"):
        kind, target = "python", "plugin.ayu.py"
    elif lower.endswith(".lua"):
        kind, target = "lua", "plugin.ayu.lua"
    elif lower.endswith(".js"):
        kind, target = "js", "plugin.ayu.js"
    else:
        raise Refused("Поддерживаются шрифты .ttf/.otf и плагины .ayu.js, .ayu.py, .ayu.lua, .wasm и .iosplug.")
    with tempfile.TemporaryDirectory() as tmp:
        # build_index wants the file in a folder named after the plugin id; read the id first.
        fields = plugin_fields(kind, data)
        pid = fields.get("id", "")
        if not ID.match(pid):
            raise Refused("@id плагина должен состоять из a-z, 0-9, - и _ (до 64 символов).")
        folder = Path(tmp) / "plugins" / pid
        folder.mkdir(parents=True)
        (folder / target).write_bytes(data)
        errors = []
        if kind == "iosplug":
            entry = build_index.iosplug_entry(folder, folder / target, errors)
            if errors or not entry:
                raise Refused("Карточка .iosplug не прошла проверку: " + "; ".join(errors))
        else:
            missing = [key for key in ("id", "name", "version", "description") if not fields.get(key)]
            if missing:
                raise Refused("В заголовке плагина нет полей: " + ", ".join("@" + m for m in missing))
            limit = build_index.MAX_WASM_BYTES if kind == "wasm" else build_index.MAX_BYTES
            if len(data) > limit:
                raise Refused(f"Плагин больше {limit // 1024} КБ.")
    return Item(kind=kind, id=pid, name=fields.get("name", pid)[:64], version=fields.get("version", "")[:32],
                description=fields.get("description", fields.get("summary", ""))[:1024], filename=target, data=data,
                injects=str(fields.get("inject", "")).lower() in ("true", "yes", "1"))


def plugin_fields(kind, data):
    if kind == "wasm":
        try:
            manifest = build_index.wasm_manifest(data)
        except (IndexError, UnicodeDecodeError, json.JSONDecodeError):
            manifest = None
        if not isinstance(manifest, dict):
            raise Refused("В plugin.wasm нет секции ayu.manifest.")
        fields = {key: str(value) for key, value in manifest.items() if isinstance(value, (str, bool, int, float))}
        fields["inject"] = "true" if manifest.get("inject") is True else "false"
        return fields
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise Refused("Файл плагина должен быть в UTF-8.")
    if kind == "iosplug":
        try:
            card = json.loads(text)
        except json.JSONDecodeError:
            raise Refused("Карточка .iosplug — это не JSON.")
        if card.get("format") == "ayu-iosplug-2" and isinstance(card.get("adapter"), dict):
            return {key: str(value) for key, value in card["adapter"].items() if isinstance(value, (str, int, float))}
        return {key: str(value) for key, value in card.items() if isinstance(value, (str, int, float))}
    comment = {"python": "#", "lua": "--"}.get(kind, "//")
    return build_index.header(text, comment)


def sign(data, key):
    """Base64 Ed25519 signature of the file, as tools/sign.py writes it."""
    with tempfile.NamedTemporaryFile() as source, tempfile.NamedTemporaryFile() as out:
        source.write(data)
        source.flush()
        subprocess.run(["openssl", "pkeyutl", "-sign", "-inkey", str(key), "-rawin", "-in", source.name, "-out", out.name], check=True)
        return base64.b64encode(Path(out.name).read_bytes()).decode()


def changes(item, author, description, existing_files, signatures=None, signature=None, by=None):
    """Repository files to write (bytes) or delete (None) for publishing `item`.

    existing_files: paths already in the item's folder (other plugin files there are removed so
    build_index does not pick a stale one). signatures: current signatures.json (plugins only).
    """
    result = {}
    keep = {f"{item.folder}/{item.filename}", f"{item.folder}/meta.json", f"{item.folder}/font.json"}
    for path in existing_files:
        name = path.rsplit("/", 1)[-1]
        if path not in keep and (name in PLUGIN_FILES or name in ("font.ttf", "font.otf")):
            result[path] = None
    result[f"{item.folder}/{item.filename}"] = item.data
    if item.is_font:
        meta = {"name": item.name, "author": author, "description": description}
        result[f"{item.folder}/font.json"] = (json.dumps(meta, ensure_ascii=False, indent=2) + "\n").encode()
    else:
        meta = {"author": author, "description": description, "official": signature is not None}
        if by:
            meta["added_by"] = str(by)
        result[f"{item.folder}/meta.json"] = (json.dumps(meta, ensure_ascii=False, indent=2) + "\n").encode()
        updated = dict(signatures or {})
        if signature is not None:
            updated[item.id] = {"sha256": item.sha256, "signature": signature}
        else:
            updated.pop(item.id, None)
        if updated != (signatures or {}):
            result["signatures.json"] = (json.dumps(updated, indent=2, sort_keys=True) + "\n").encode()
    return result


def removal(kind, item_id, existing_files, signatures=None):
    """Files to delete when an item leaves the catalog."""
    result = {path: None for path in existing_files}
    if kind != "font" and signatures and item_id in signatures:
        updated = dict(signatures)
        updated.pop(item_id)
        result["signatures.json"] = (json.dumps(updated, indent=2, sort_keys=True) + "\n").encode()
    return result
