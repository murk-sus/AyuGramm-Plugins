#!/usr/bin/env python3
"""Sign every catalog plugin with the VoidGram Ed25519 key and write signatures.json.

The private key never enters the repository. It is read from $AYU_SIGNING_KEY or
~/.config/ayugram-plugins/signing-key.pem. Run after changing a plugin, then build_index.py:

    python3 tools/sign.py && python3 tools/build_index.py

A signed plugin counts as official in VoidGram, so it may inject into the app (player, lyrics).
Only sign plugins whose code you have reviewed.
"""
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ("plugin.ayu.js", "plugin.ayu.py", "plugin.ayu.lua", "plugin.wasm", "plugin.iosplug")


def main():
    key = Path(os.environ.get("AYU_SIGNING_KEY", Path.home() / ".config/ayugram-plugins/signing-key.pem"))
    if not key.is_file():
        print(f"signing key not found: {key}", file=sys.stderr)
        return 1
    result = {}
    for folder in sorted((ROOT / "plugins").iterdir()):
        path = next((folder / name for name in FILES if (folder / name).is_file()), None)
        if path is None:
            continue
        # Plugins by other authors (meta.json from the team bot) are signed only when the team
        # marked them official there; this script must never promote them silently.
        meta = folder / "meta.json"
        if meta.is_file() and json.loads(meta.read_text(encoding="utf-8")).get("official") is not True:
            continue
        data = path.read_bytes()
        with tempfile.NamedTemporaryFile() as out:
            subprocess.run(["openssl", "pkeyutl", "-sign", "-inkey", str(key), "-rawin", "-in", str(path), "-out", out.name], check=True)
            signature = Path(out.name).read_bytes()
        result[folder.name] = {"sha256": hashlib.sha256(data).hexdigest(), "signature": base64.b64encode(signature).decode()}
    (ROOT / "signatures.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"signatures.json: {len(result)} plugins signed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
