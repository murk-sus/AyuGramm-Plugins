#!/usr/bin/env python3
"""Write fonts/index.json, the font catalog AyuGram downloads.

Each font lives in fonts/<id>/ with one font.ttf or font.otf and a font.json:

    {"name": "My Font", "author": "someone", "description": "Optional, one line"}

The id must equal the folder name (a-z, 0-9, - and _). The index carries the SHA-256 of each
file; the app refuses a download that does not match.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = "https://raw.githubusercontent.com/murk-sus/AyuGramm-Plugins/main/"
ID = re.compile(r"^[a-z0-9_-]{1,64}$")
MAX_BYTES = 15 * 1024 * 1024


def main():
    errors, fonts = [], []
    folder_root = ROOT / "fonts"
    folder_root.mkdir(exist_ok=True)
    for folder in sorted(path for path in folder_root.iterdir() if path.is_dir()):
        font = next((folder / name for name in ("font.ttf", "font.otf") if (folder / name).is_file()), None)
        meta_path = folder / "font.json"
        if not ID.match(folder.name):
            errors.append(f"{folder.name}: id must use a-z 0-9 - _")
            continue
        if font is None or not meta_path.is_file():
            errors.append(f"{folder.name}: needs font.ttf or font.otf and font.json")
            continue
        data = font.read_bytes()
        if len(data) > MAX_BYTES:
            errors.append(f"{folder.name}: larger than 15 MB")
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            errors.append(f"{folder.name}: font.json is not JSON")
            continue
        if not meta.get("name"):
            errors.append(f"{folder.name}: font.json needs a name")
            continue
        fonts.append({
            "id": folder.name,
            "name": str(meta["name"])[:64],
            "author": str(meta.get("author", ""))[:128],
            "description": str(meta.get("description", ""))[:300],
            "url": RAW + f"fonts/{folder.name}/{font.name}",
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
        })
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    (folder_root / "index.json").write_text(json.dumps({"format": "ayugram-font-catalog", "version": 1, "fonts": fonts}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"fonts/index.json: {len(fonts)} fonts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
