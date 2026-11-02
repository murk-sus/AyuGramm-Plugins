import importlib.util
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import catalog  # noqa: E402
import build_index  # noqa: E402
import build_readme  # noqa: E402

spec = importlib.util.spec_from_file_location("verify_bot_catalog", HERE / "bot.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

FONT = (REPO / "fonts/dream-font/font.ttf").read_bytes()
JS = b"""// ==AyuPlugin==
// @id my-plugin
// @name My plugin
// @author someone
// @version 1.2
// @description Trims outgoing text.
// ==/AyuPlugin==
ayu.hooks.before(ayu.hooks.points.outgoingText, (text) => text.trim());
"""
LUA = b"""-- ==AyuPlugin==
-- @id lua-thing
-- @name Lua thing
-- @author someone
-- @version 0.1
-- @description Says hi.
-- ==/AyuPlugin==
ayu.log("hi")
"""


def without_postscript(data):
    """The same font with its PostScript name records renumbered, as in fonts that lack one."""
    import struct
    data = bytearray(data)
    count = struct.unpack(">H", data[4:6])[0]
    for i in range(count):
        tag, _, offset, _ = struct.unpack(">4sIII", data[12 + 16 * i:28 + 16 * i])
        if tag == b"name":
            records = struct.unpack(">H", data[offset + 2:offset + 4])[0]
            for r in range(records):
                at = offset + 6 + 12 * r + 6
                if struct.unpack(">H", data[at:at + 2])[0] == 6:
                    data[at:at + 2] = struct.pack(">H", 7)
    return bytes(data)


class InspectTests(unittest.TestCase):
    def test_font(self):
        item = catalog.inspect("DreamFont.ttf", FONT)
        self.assertEqual((item.kind, item.id, item.name, item.filename), ("font", "dreamfont", "DreamFont", "font.ttf"))
        self.assertEqual(item.folder, "fonts/dreamfont")

    def test_font_without_postscript_name_is_refused(self):
        with self.assertRaises(catalog.Refused):
            catalog.inspect("x.ttf", without_postscript(FONT))

    def test_not_a_font(self):
        with self.assertRaises(catalog.Refused):
            catalog.inspect("fake.ttf", b"<html>not a font</html>")

    def test_js_plugin(self):
        item = catalog.inspect("my.ayu.js", JS)
        self.assertEqual((item.kind, item.id, item.version, item.filename), ("js", "my-plugin", "1.2", "plugin.ayu.js"))
        self.assertEqual(item.description, "Trims outgoing text.")

    def test_lua_plugin(self):
        item = catalog.inspect("thing.ayu.lua", LUA)
        self.assertEqual((item.kind, item.id, item.filename), ("lua", "lua-thing", "plugin.ayu.lua"))

    def test_missing_header_field(self):
        with self.assertRaises(catalog.Refused):
            catalog.inspect("my.ayu.js", JS.replace(b"// @description Trims outgoing text.\n", b""))

    def test_bad_id(self):
        with self.assertRaises(catalog.Refused):
            catalog.inspect("my.ayu.js", JS.replace(b"@id my-plugin", b"@id ../../etc"))

    def test_unknown_extension_and_encoding(self):
        with self.assertRaises(catalog.Refused):
            catalog.inspect("archive.zip", b"PK")
        with self.assertRaises(catalog.Refused):
            catalog.inspect("my.ayu.js", b"\xff\xfe\x00")


class ChangesTests(unittest.TestCase):
    def test_font_files(self):
        item = catalog.inspect("DreamFont.ttf", FONT)
        files = catalog.changes(item, "@lwwlt", "Hand drawn", ["fonts/dreamfont/font.otf", "fonts/dreamfont/font.json"])
        self.assertIsNone(files["fonts/dreamfont/font.otf"])  # a stale file of the other type goes away
        self.assertEqual(files["fonts/dreamfont/font.ttf"], FONT)
        self.assertEqual(json.loads(files["fonts/dreamfont/font.json"]), {"name": "DreamFont", "author": "@lwwlt", "description": "Hand drawn"})
        self.assertNotIn("signatures.json", files)

    def test_signed_plugin(self):
        item = catalog.inspect("my.ayu.js", JS)
        files = catalog.changes(item, "@author_x", "", ["plugins/my-plugin/plugin.ayu.py"], {"other": {"sha256": "a", "signature": "b"}}, "SIG", by=1)
        self.assertIsNone(files["plugins/my-plugin/plugin.ayu.py"])
        meta = json.loads(files["plugins/my-plugin/meta.json"])
        self.assertEqual((meta["author"], meta["official"], meta["added_by"]), ("@author_x", True, "1"))
        signatures = json.loads(files["signatures.json"])
        self.assertEqual(signatures["my-plugin"], {"sha256": item.sha256, "signature": "SIG"})
        self.assertIn("other", signatures)

    def test_unsigned_update_drops_old_signature(self):
        item = catalog.inspect("my.ayu.js", JS)
        files = catalog.changes(item, "@author_x", "", [], {"my-plugin": {"sha256": "old", "signature": "old"}}, None)
        self.assertEqual(json.loads(files["signatures.json"]), {})
        self.assertFalse(json.loads(files["plugins/my-plugin/meta.json"])["official"])

    def test_removal(self):
        files = catalog.removal("plugin", "my-plugin", ["plugins/my-plugin/plugin.ayu.js", "plugins/my-plugin/meta.json"],
                                {"my-plugin": {"sha256": "x", "signature": "y"}})
        self.assertEqual(files["plugins/my-plugin/plugin.ayu.js"], None)
        self.assertEqual(json.loads(files["signatures.json"]), {})


class BuildTests(unittest.TestCase):
    def test_index_meta_and_lua(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "plugins/lua-thing").mkdir(parents=True)
            (root / "plugins/lua-thing/plugin.ayu.lua").write_bytes(LUA)
            (root / "plugins/lua-thing/meta.json").write_text(json.dumps({"author": "@lwwlt", "description": "Better text"}))
            (root / "plugins/my-plugin").mkdir(parents=True)
            (root / "plugins/my-plugin/plugin.ayu.js").write_bytes(JS)
            with patch.object(build_index, "ROOT", root):
                self.assertEqual(build_index.main(), 0)
            entries = {e["id"]: e for e in json.loads((root / "index.json").read_text())["plugins"]}
            self.assertEqual((entries["lua-thing"]["kind"], entries["lua-thing"]["author"], entries["lua-thing"]["description"]), ("lua", "@lwwlt", "Better text"))
            self.assertEqual(entries["my-plugin"]["author"], build_index.CATALOG_AUTHOR)  # no meta.json: the team

    def test_readme_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "fonts").mkdir()
            (root / "plugins/lua-thing").mkdir(parents=True)
            (root / "plugins/lua-thing/meta.json").write_text("{}")
            (root / "fonts/index.json").write_text(json.dumps({"fonts": [{"id": "a", "name": "A | B", "author": "@lwwlt", "description": "x", "url": "https://r/main/fonts/a/font.ttf"}]}))
            (root / "index.json").write_text(json.dumps({"plugins": [{"id": "lua-thing", "name": "Lua thing", "author": "@lwwlt", "kind": "lua", "version": "0.1", "description": "d", "url": "https://r/main/plugins/lua-thing/plugin.ayu.lua"}]}))
            (root / "README.md").write_text("# Title\n\nIntro\n\n## Installing\n\nText\n")
            with patch.object(build_readme, "ROOT", root):
                build_readme.main()
                first = (root / "README.md").read_text()
                build_readme.main()
            self.assertEqual(first, (root / "README.md").read_text())
            self.assertIn("| [A \\| B](fonts/a/font.ttf) | [@lwwlt](https://t.me/lwwlt) | x |", first)
            self.assertIn("## Plugins by other authors", first)
            self.assertLess(first.index("catalog:end"), first.index("## Installing"))


class BotUploadTests(unittest.TestCase):
    def setUp(self):
        self.sender = min(bot.TEAM)
        self.user = {"hash": "test", "salt": "00", "session": time.time() + 600, "step": "menu"}
        self.state = {"users": {str(self.sender): self.user}, "refused": []}
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sent = []
        self.patch("UPLOADS", Path(self.tmp.name))
        self.patch("PLUGIN_KEY", Path(self.tmp.name) / "missing.pem")
        self.patch("send", side_effect=lambda chat, text, buttons=None: self.sent.append((text, buttons)))
        self.patch("call")
        self.patch("log")
        self.patch("folder_files", return_value=[])
        self.patch("read_json", side_effect=lambda path, default: default)
        self.commit = self.patch("commit", return_value="abc123")
        self.report = self.patch("report_when_built")
        self.download = self.patch("download")

    def patch(self, name, value=None, **kwargs):
        patcher = patch.object(bot, name, value, **kwargs) if value is not None else patch.object(bot, name, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def message(self, text="", document=None, sender=None):
        message = {"chat": {"id": 5, "type": "private"}, "from": {"id": sender or self.sender}, "text": text, "message_id": 1}
        if document:
            message["document"] = document
        bot.handle_message(self.state, message)

    def callback(self, data):
        bot.handle_callback(self.state, {"id": "q", "from": {"id": self.sender}, "message": {"chat": {"id": 5, "type": "private"}}, "data": data})

    def test_font_upload(self):
        self.callback("upload")
        self.download.return_value = FONT
        self.message(document={"file_id": "f", "file_name": "DreamFont.ttf", "file_size": len(FONT)})
        self.assertEqual(self.user["step"], "upload_author")
        self.message("lwwlt")
        self.assertEqual(self.user["upload"]["author"], "@lwwlt")
        self.message("Рисованный шрифт")
        self.assertEqual(self.user["step"], "upload_confirm")
        self.callback("u:publish")
        files, message = self.commit.call_args.args
        self.assertEqual(files["fonts/dreamfont/font.ttf"], FONT)
        self.assertEqual(json.loads(files["fonts/dreamfont/font.json"])["author"], "@lwwlt")
        self.assertIn("by @lwwlt", message)
        self.report.assert_called_once()
        self.assertEqual(self.user["step"], "menu")
        self.assertNotIn("upload", self.user)
        self.assertFalse(any(Path(self.tmp.name).iterdir()))  # the upload copy is removed

    def test_plugin_upload_keeps_header_description(self):
        self.callback("upload")
        self.download.return_value = JS
        self.message(document={"file_id": "f", "file_name": "my.ayu.js", "file_size": len(JS)})
        self.message("@some_author")
        self.message("-")
        self.callback("u:publish")
        files = self.commit.call_args.args[0]
        meta = json.loads(files["plugins/my-plugin/meta.json"])
        self.assertEqual((meta["description"], meta["official"]), ("Trims outgoing text.", False))

    def test_refused_file_keeps_waiting(self):
        self.callback("upload")
        self.download.return_value = b"nope"
        self.message(document={"file_id": "f", "file_name": "x.ttf", "file_size": 4})
        self.assertEqual(self.user["step"], "upload_file")
        self.commit.assert_not_called()

    def test_bad_nick(self):
        self.callback("upload")
        self.download.return_value = FONT
        self.message(document={"file_id": "f", "file_name": "DreamFont.ttf", "file_size": len(FONT)})
        self.message("no spaces allowed")
        self.assertEqual(self.user["step"], "upload_author")

    def test_document_without_upload_step_is_ignored(self):
        self.message(document={"file_id": "f", "file_name": "DreamFont.ttf", "file_size": 10})
        self.download.assert_not_called()

    def test_outsider_cannot_upload(self):
        outsider = max(bot.TEAM) + 1
        self.message(document={"file_id": "f", "file_name": "DreamFont.ttf", "file_size": 10}, sender=outsider)
        self.download.assert_not_called()
        self.assertIn(outsider, self.state["refused"])

    def test_cancel_drops_upload(self):
        self.callback("upload")
        self.download.return_value = FONT
        self.message(document={"file_id": "f", "file_name": "DreamFont.ttf", "file_size": len(FONT)})
        self.message("/cancel")
        self.assertNotIn("upload", self.user)
        self.assertFalse(any(Path(self.tmp.name).iterdir()))

    def test_removal(self):
        self.patch("folder_files", return_value=["fonts/dream-font/font.ttf", "fonts/dream-font/font.json"])
        self.callback("remove")
        self.message("шрифт dream-font")
        self.callback("r:yes")
        files = self.commit.call_args.args[0]
        self.assertEqual(files, {"fonts/dream-font/font.ttf": None, "fonts/dream-font/font.json": None})


if __name__ == "__main__":
    unittest.main()
