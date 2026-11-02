import importlib.util
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("verify_bot_team", Path(__file__).with_name("bot.py"))
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

MEMBER = 7556953433
NEWCOMER = 1234567890


class TeamTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name) / "team.json"
        self.sent = []
        for name, kwargs in (("team_path", {"return_value": self.file}), ("UPLOADS", {"new": Path(self.tmp.name) / "uploads"}),
                             ("call", {}), ("log", {}),
                             ("send", {"side_effect": lambda chat, text, buttons=None: self.sent.append((chat, text, buttons))})):
            patcher = patch.object(bot, name, **kwargs)
            self.addCleanup(patcher.stop)
            patcher.start()
        now = time.time() + 600
        self.state = {"users": {str(bot.OWNER): {"hash": "h", "salt": "00", "session": now, "step": "menu"},
                                str(MEMBER): {"hash": "h", "salt": "00", "session": now, "step": "upload_author"}},
                      "refused": [NEWCOMER]}

    def message(self, sender, text):
        bot.handle_message(self.state, {"chat": {"id": sender, "type": "private"}, "from": {"id": sender}, "text": text, "message_id": 1})

    def callback(self, sender, data):
        bot.handle_callback(self.state, {"id": "q", "from": {"id": sender}, "message": {"chat": {"id": sender, "type": "private"}}, "data": data})

    def test_without_file_the_built_in_team(self):
        self.assertEqual(bot.team(), bot.TEAM)

    def test_owner_adds_a_member(self):
        self.callback(bot.OWNER, "t:add")
        self.message(bot.OWNER, str(NEWCOMER))
        self.assertIn(NEWCOMER, bot.team())
        self.assertNotIn(NEWCOMER, self.state["refused"])
        self.assertIn(NEWCOMER, json.loads(self.file.read_text())["members"])
        self.message(NEWCOMER, "/start")  # the newcomer is let in and asked for a password
        self.assertEqual(self.state["users"][str(NEWCOMER)]["step"], "set_password")

    def test_owner_removes_a_member_and_access_ends(self):
        self.callback(bot.OWNER, "t:remove")
        self.message(bot.OWNER, str(MEMBER))
        self.assertNotIn(MEMBER, bot.team())
        self.assertNotIn(str(MEMBER), self.state["users"])
        self.sent.clear()
        self.message(MEMBER, "@someone")
        self.assertEqual(self.sent[-1][1], "⛔ Доступ запрещён.")
        self.assertIn(MEMBER, self.state["refused"])

    def test_owner_cannot_be_removed(self):
        self.callback(bot.OWNER, "t:remove")
        self.message(bot.OWNER, str(bot.OWNER))
        self.assertIn(bot.OWNER, bot.team())
        self.file.write_text(json.dumps({"members": [MEMBER]}))
        self.assertIn(bot.OWNER, bot.team())  # even a hand-edited file keeps the owner

    def test_members_cannot_manage_the_team(self):
        for data in ("team", "t:add", "t:remove"):
            self.callback(MEMBER, data)
        self.assertNotIn(self.state["users"][str(MEMBER)].get("step"), ("team_add", "team_remove"))
        # Even with the step forced, the change itself checks the sender.
        self.state["users"][str(MEMBER)]["step"] = "team_add"
        self.message(MEMBER, str(NEWCOMER))
        self.assertNotIn(NEWCOMER, bot.team())
        self.assertFalse(self.file.exists())

    def test_only_the_owner_sees_the_button(self):
        bot.menu(bot.OWNER)
        bot.menu(MEMBER)
        owner_buttons = [data for _, data in self.sent[0][2]]
        member_buttons = [data for _, data in self.sent[1][2]]
        self.assertIn("team", owner_buttons)
        self.assertNotIn("team", member_buttons)

    def test_bad_ids_are_refused(self):
        self.callback(bot.OWNER, "t:add")
        for text in ("abc", "-5", "0", "١٢٣"):
            self.message(bot.OWNER, text)
        self.assertEqual(bot.team(), bot.TEAM)

    def test_damaged_file_does_not_open_the_bot(self):
        self.file.write_text("{not json")
        with self.assertRaises(Exception):
            json.loads(self.file.read_text())
        self.file.write_text(json.dumps({"members": ["x"]}))
        self.assertEqual(bot.team(), bot.TEAM)
