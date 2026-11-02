import copy
import importlib.util
from pathlib import Path
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("verify_bot", Path(__file__).with_name("bot.py"))
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)


class BannerTests(unittest.TestCase):
    def setUp(self):
        self.sender = min(bot.TEAM)
        self.user = {"hash": "test", "session": time.time() + 600, "step": "menu"}
        self.state = {"users": {str(self.sender): self.user}, "refused": []}
        self.registry = {"format": "ayugram-verified", "entries": [
            {"id": "123", "kind": "developer", "text": "Developer", "by": "team", "at": 1}
        ]}
        self.send = self.start_patch("send")
        self.start_patch("call")
        self.start_patch("log")
        self.start_patch("load_registry", side_effect=lambda: copy.deepcopy(self.registry))
        self.publish = self.start_patch("publish")

    def start_patch(self, name, **kwargs):
        patcher = patch.object(bot, name, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def message(self, text, sender=None, chat_type="private"):
        bot.handle_message(self.state, {"chat": {"id": self.sender, "type": chat_type},
                                       "from": {"id": self.sender if sender is None else sender},
                                       "text": text, "message_id": 1})

    def test_set_preserves_badge(self):
        self.message("/banner 00123 https://images.example/banner.png")
        result = self.publish.call_args.args[0]["entries"][0]
        self.assertEqual(result, dict(self.registry["entries"][0], banner="https://images.example/banner.png"))
        self.assertEqual(self.user["step"], "menu")
        self.assertNotIn("target", self.user)

    def test_remove_preserves_badge(self):
        self.registry["entries"][0]["banner"] = "https://images.example/old.png"
        self.message("/banner 123 -")
        result = self.publish.call_args.args[0]["entries"][0]
        self.assertNotIn("banner", result)
        self.assertEqual(result["text"], "Developer")

    def test_unknown_user_does_not_get_verification(self):
        self.message("/banner 456 https://images.example/banner.png")
        self.publish.assert_not_called()

    def test_invalid_urls_never_publish(self):
        for url in ("http://example.com/a", "https://", "https://u:p@example.com/a",
                    "https://example.com/a#fragment", "https://example.com/a#", "https://example.com:70000/a",
                    "https://example.com/a b", "https://example.com/\\a",
                    "https://[broken/a", "https://example.com/" + "x" * 512):
            with self.subTest(url=url):
                self.message("/banner 123 " + url)
        self.publish.assert_not_called()

    def test_invalid_ids_never_publish(self):
        for target in ("0", "-1", "abc", "١٢٣", str(2 ** 63)):
            self.message(f"/banner {target} https://example.com/a.png")
        self.publish.assert_not_called()

    def test_authentication_and_private_chat_required(self):
        self.message("/banner 123 https://example.com/a.png", sender=1)
        self.message("/banner 123 https://example.com/a.png", chat_type="group")
        self.user["session"] = 0
        self.message("/banner 123 https://example.com/a.png")
        self.publish.assert_not_called()

    def test_menu_flow_and_cancel(self):
        bot.handle_callback(self.state, {"id": "callback", "from": {"id": self.sender},
            "message": {"chat": {"id": self.sender, "type": "private"}}, "data": "banner"})
        self.assertEqual(self.user["step"], "banner_id")
        self.message("123")
        self.assertEqual(self.user["step"], "banner_url")
        self.message("/cancel")
        self.assertEqual(self.user["step"], "menu")
        self.assertNotIn("target", self.user)
        self.publish.assert_not_called()

    def test_failed_publish_can_be_retried(self):
        self.publish.side_effect = OSError("offline")
        with self.assertRaises(OSError):
            self.message("/banner 123 https://example.com/a.png")
        self.assertEqual(self.user["target"], "123")
        self.assertEqual(self.user["step"], "banner_url")
        self.publish.side_effect = None
        self.message("https://example.com/a.png")
        self.assertEqual(self.user["step"], "menu")

    def test_changing_badge_keeps_banner(self):
        self.registry["entries"][0]["banner"] = "https://example.com/a.png"
        self.user["target"] = "123"
        bot.grant(self.state, self.sender, self.sender, self.user, "custom", "New label")
        entry = self.publish.call_args.args[0]["entries"][0]
        self.assertEqual(entry["banner"], "https://example.com/a.png")
        self.assertEqual(entry["text"], "New label")


if __name__ == "__main__":
    unittest.main()
