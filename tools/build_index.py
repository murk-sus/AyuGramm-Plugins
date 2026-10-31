#!/usr/bin/env python3
"""Validate every plugin and write index.json, the catalog AyuGram downloads.

Each plugin lives in plugins/<id>/ as either
- plugin.ayu.js: a JavaScript code plugin with an `// ==AyuPlugin==` header (kind "js"), or
- plugin.iosplug: a native plugin card, `ayu-iosplug-1` or `ayu-iosplug-2` (kind "iosplug").
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
MAX_IOSPLUG_BYTES = 64 * 1024


def header(source):
    fields = {}
    for line in source.splitlines()[:80]:
        match = re.match(r"\s*//\s*@(\w+)\s*(.*)$", line)
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
    for folder in sorted((ROOT / "plugins").iterdir()):
        if not folder.is_dir():
            continue
        card = folder / "plugin.iosplug"
        if card.is_file():
            entry = iosplug_entry(folder, card, errors)
            if entry:
                entries.append(entry)
            continue
        path = folder / "plugin.ayu.js"
        if not path.is_file():
            errors.append(f"{folder.name}: missing plugin.ayu.js or plugin.iosplug")
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
        fields = header(source)
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
            "kind": "js",
            "url": RAW + f"plugins/{folder.name}/plugin.ayu.js",
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
        })
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    index = {"format": "ayugram-plugin-catalog", "version": 1, "plugins": entries}
    (ROOT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"index.json: {len(entries)} plugins")
    return 0


if __name__ == "__main__":
    sys.exit(main())
