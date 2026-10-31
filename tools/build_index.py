#!/usr/bin/env python3
"""Validate every plugin and write index.json, the catalog AyuGram downloads.

Each plugin lives in plugins/<id>/ as either
- plugin.ayu.js: a JavaScript code plugin with an `// ==AyuPlugin==` header (kind "js"), or
- plugin.ayu.py: a Python plugin with a `# ==AyuPlugin==` header (kind "python"),
- plugin.wasm: a Rust/WebAssembly plugin with an `ayu.manifest` custom section (kind "wasm"),
- plugin.iosplug: a native plugin card, `ayu-iosplug-1` or `ayu-iosplug-2` (kind "iosplug").
`@inject true` (or `"inject": true`) marks plugins that change the app itself (player, lyrics);
the app installs those only with an AyuGram signature, which tools/sign.py writes to
signatures.json with the private key kept outside the repository.
The index carries the SHA-256 of each file; the app refuses a download that does not match.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = "https://raw.githubusercontent.com/murk-sus/AyuGramm-Plugins/main/"
ID = re.compile(r"^[a-z0-9_-]{1,64}$")
REQUIRED = ("id", "name", "author", "version", "description")
MAX_BYTES = 512 * 1024
# Every plugin in this catalog is made and maintained by the AyuGramm team.
CATALOG_AUTHOR = "murk-sus & dsn2fvhmn4-lgtm"
MAX_IOSPLUG_BYTES = 64 * 1024
MAX_WASM_BYTES = 2 * 1024 * 1024


def signatures():
    path = ROOT / "signatures.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def wasm_manifest(data):
    """The JSON of the `ayu.manifest` custom section, or None."""
    def leb(i):
        result = shift = 0
        while True:
            b = data[i]; i += 1
            result |= (b & 0x7f) << shift
            if b < 0x80:
                return result, i
            shift += 7
    if data[:4] != b"\0asm":
        return None
    i = 8
    while i < len(data):
        sid = data[i]; i += 1
        size, i = leb(i)
        end = i + size
        if sid == 0:
            n, j = leb(i)
            if data[j:j + n] == b"ayu.manifest":
                return json.loads(data[j + n:end].decode("utf-8"))
        i = end
    return None


def header(source, comment="//"):
    fields = {}
    for line in source.splitlines()[:80]:
        match = re.match(r"\s*" + re.escape(comment) + r"\s*@(\w+)\s*(.*)$", line)
        if match:
            fields[match.group(1).lower()] = match.group(2).strip()
    return fields


def iosplug_entry(folder, path, errors):
    data = path.read_bytes()
    if len(data) > MAX_IOSPLUG_BYTES:
        errors.append(f"{folder.name}: .iosplug larger than 64 KB")
        return None
    try:
        card = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        errors.append(f"{folder.name}: .iosplug is not UTF-8 JSON")
        return None
    if card.get("format") == "ayu-iosplug-2" and isinstance(card.get("adapter"), dict):
        fields = card["adapter"]
        description = fields.get("summary", "")
    elif card.get("format") == "ayu-iosplug-1":
        fields = card
        description = fields.get("description", "")
    else:
        errors.append(f"{folder.name}: unknown .iosplug format")
        return None
    pid = fields.get("id", "")
    if pid != folder.name or not ID.match(pid):
        errors.append(f"{folder.name}: card id must equal the folder name")
        return None
    if not all(fields.get(key) for key in ("name", "author", "version")):
        errors.append(f"{folder.name}: card lacks name, author or version")
        return None
    return {
        "id": pid,
        "name": fields["name"][:64],
        "author": fields["author"][:128],
        "version": fields["version"][:32],
        "description": description[:1024],
        "tags": ["native"],
        "kind": "iosplug",
        "url": RAW + f"plugins/{folder.name}/plugin.iosplug",
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
    }


def main():
    errors = []
    entries = []
    known = signatures()
    for folder in sorted((ROOT / "plugins").iterdir()):
        if not folder.is_dir():
            continue
        card = folder / "plugin.iosplug"
        if card.is_file():
            entry = iosplug_entry(folder, card, errors)
            if entry:
                entries.append(entry)
            continue
        wasm = folder / "plugin.wasm"
        if wasm.is_file():
            data = wasm.read_bytes()
            if len(data) > MAX_WASM_BYTES:
                errors.append(f"{folder.name}: .wasm larger than 2 MB")
                continue
            try:
                manifest = wasm_manifest(data)
            except (IndexError, UnicodeDecodeError, json.JSONDecodeError):
                manifest = None
            if not isinstance(manifest, dict):
                errors.append(f"{folder.name}: plugin.wasm lacks an ayu.manifest section")
                continue
            fields = {key: str(value) for key, value in manifest.items() if isinstance(value, (str, bool))}
            fields["tags"] = ", ".join(manifest.get("tags", [])) if isinstance(manifest.get("tags"), list) else fields.get("tags", "")
            fields["inject"] = "true" if manifest.get("inject") is True else "false"
            kind, filename = "wasm", "plugin.wasm"
        else:
            if (folder / "plugin.ayu.py").is_file():
                path, kind, filename, comment = folder / "plugin.ayu.py", "python", "plugin.ayu.py", "#"
            else:
                path, kind, filename, comment = folder / "plugin.ayu.js", "js", "plugin.ayu.js", "//"
            if not path.is_file():
                errors.append(f"{folder.name}: missing plugin.ayu.js, plugin.ayu.py, plugin.wasm or plugin.iosplug")
                continue
            data = path.read_bytes()
            if len(data) > MAX_BYTES:
                errors.append(f"{folder.name}: larger than 512 KB")
                continue
            try:
                source = data.decode("utf-8")
            except UnicodeDecodeError:
                errors.append(f"{folder.name}: not UTF-8")
                continue
            fields = header(source, comment)
        missing = [key for key in REQUIRED if not fields.get(key)]
        if missing:
            errors.append(f"{folder.name}: header lacks {', '.join(missing)}")
            continue
        if fields["id"] != folder.name or not ID.match(fields["id"]):
            errors.append(f"{folder.name}: @id must equal the folder name and use a-z 0-9 - _")
            continue
        entries.append({
            "id": fields["id"],
            "name": fields["name"][:64],
            "author": fields["author"][:128],
            "version": fields["version"][:32],
            "description": fields["description"][:1024],
            "tags": [tag.strip() for tag in fields.get("tags", "").split(",") if tag.strip()][:8],
            "kind": kind,
            "injects": fields.get("inject", "").lower() in ("true", "yes", "1"),
            "url": RAW + f"plugins/{folder.name}/{filename}",
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
        })

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    # Official plugins: the signature from signatures.json, only while the file is unchanged.
    for entry in entries:
        entry["author"] = CATALOG_AUTHOR
        signed = known.get(entry["id"])
        if signed and signed.get("sha256") == entry["sha256"]:
            entry["signature"] = signed["signature"]
    index = {"format": "ayugram-plugin-catalog", "version": 1, "plugins": entries}
    (ROOT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"index.json: {len(entries)} plugins")
    return 0


if __name__ == "__main__":
    sys.exit(main())
