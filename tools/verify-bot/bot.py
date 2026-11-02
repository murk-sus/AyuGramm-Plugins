#!/usr/bin/env python3
"""@ayugram_dev_settings_bot: AyuGram for iOS team verification.

Only the team's Telegram IDs may use it; everyone else is refused. Each team member sets a
password (typed twice) and enters it to unlock the bot. Then they can grant or revoke the
"verified by the AyuGram for iOS team" label for a Telegram user, with a custom text or one of
the classic ones.

The list lives in registry/verified.json of github.com/murk-sus/AyuGramm-Plugins, signed with
Ed25519 (registry/verified.json.sig). Every AyuGram client downloads it, checks the signature
with the public key built into the app and shows the label.

Secrets stay on this machine, never in the repository:
  ~/.config/ayugram-bot/token             the bot token
  ~/.config/ayugram-bot/registry-key.pem  the registry signing key
  ~/.config/ayugram-bot/state.json        password hashes and conversation state
GitHub access uses the `gh` login of this machine.

Standard library only:  python3 tools/verify-bot/bot.py
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TEAM = {7556953433, 7864640050, 7754143736, 8276132300}
CONFIG = Path(os.environ.get("AYU_BOT_CONFIG", Path.home() / ".config/ayugram-bot"))
REPO = "murk-sus/AyuGramm-Plugins"
REGISTRY_PATH = "registry/verified.json"
GH = os.environ.get("AYU_BOT_GH", str(Path.home() / ".local/bin/gh"))
SESSION_SECONDS = 30 * 60
MAX_ATTEMPTS = 5
LOCK_SECONDS = 15 * 60

CLASSIC = {
    "sponsor": "Этот пользователь спонсирует AyuGram",
    "developer": "Этот человек является разработчиком AyuGram",
    "plugins": "Этот человек официально подтверждён как создатель плагинов для AyuGram",
}

TOKEN = (CONFIG / "token").read_text().strip()
API = f"https://api.telegram.org/bot{TOKEN}/"


def log(*parts):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), *parts, flush=True)


# MARK: Telegram

def call(method, **params):
    data = urllib.parse.urlencode({key: json.dumps(value) if isinstance(value, (dict, list)) else value for key, value in params.items()}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(API + method, data=data), timeout=70) as response:
            return json.loads(response.read()).get("result")
    except urllib.error.HTTPError as error:
        log("telegram error", method, error.code, error.read()[:200])
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        log("network error", method, error)
        time.sleep(3)
    return None


def send(chat, text, buttons=None):
    params = {"chat_id": chat, "text": text}
    if buttons:
        params["reply_markup"] = {"inline_keyboard": [[{"text": title, "callback_data": data}] for title, data in buttons]}
    return call("sendMessage", **params)


# MARK: State

def load_state():
    path = CONFIG / "state.json"
    return json.loads(path.read_text()) if path.is_file() else {"users": {}, "refused": []}


def save_state(state):
    path = CONFIG / "state.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=1))
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1).hex()


# MARK: Registry on GitHub

def gh_token():
    return subprocess.run([GH, "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()


def github(method, path, body=None):
    request = urllib.request.Request(f"https://api.github.com/repos/{REPO}/contents/{path}", method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": "Bearer " + gh_token(), "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise


def load_registry():
    current = github("GET", REGISTRY_PATH + "?ref=main")
    if not current:
        return {"format": "ayugram-verified", "version": 1, "updated": 0, "entries": []}
    return json.loads(base64.b64decode(current["content"]))


def sign(data):
    with tempfile.NamedTemporaryFile() as source, tempfile.NamedTemporaryFile() as signature:
        source.write(data)
        source.flush()
        subprocess.run(["openssl", "pkeyutl", "-sign", "-inkey", str(CONFIG / "registry-key.pem"), "-rawin", "-in", source.name, "-out", signature.name], check=True)
        return base64.b64encode(Path(signature.name).read_bytes())


def publish(registry, message):
    registry["updated"] = int(time.time())
    registry["entries"].sort(key=lambda entry: int(entry["id"]))
    data = (json.dumps(registry, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode()
    for path, content in ((REGISTRY_PATH, data), (REGISTRY_PATH + ".sig", sign(data) + b"\n")):
        current = github("GET", path + "?ref=main")
        body = {"message": message, "content": base64.b64encode(content).decode(), "branch": "main"}
        if current:
            body["sha"] = current["sha"]
        github("PUT", path, body)


# MARK: Conversation

def menu(chat):
    send(chat, "Что сделать?", [("✅ Выдать надпись", "grant"), ("❌ Забрать надпись", "revoke"), ("📋 Список", "list"), ("🔒 Выйти", "logout")])


def handle_message(state, message):
    chat = message["chat"]["id"]
    sender = message.get("from", {}).get("id")
    text = (message.get("text") or "").strip()
    if message["chat"].get("type") != "private":
        return
    if sender not in TEAM:
        if sender not in state["refused"]:
            state["refused"].append(sender)
            send(chat, "⛔ Доступ запрещён.")
        log("refused", sender)
        return
    user = state["users"].setdefault(str(sender), {"step": "new"})
    step = user.get("step", "new")
    now = time.time()

    if user.get("locked_until", 0) > now:
        send(chat, f"🔒 Слишком много неверных паролей. Попробуйте через {int((user['locked_until'] - now) / 60) + 1} мин.")
        return

    # Passwords never stay in the chat.
    if step in ("set_password", "confirm_password", "password"):
        call("deleteMessage", chat_id=chat, message_id=message["message_id"])

    if step == "new" or (text == "/start" and "hash" not in user):
        user["step"] = "set_password"
        send(chat, "👋 Бот верификации AyuGram для iOS.\n\nПоставьте пароль (не короче 6 символов). Сообщение с паролем будет удалено.")
        return
    if step == "set_password":
        if len(text) < 6:
            send(chat, "Пароль должен быть не короче 6 символов. Попробуйте ещё раз.")
            return
        user["pending"] = hashlib.sha256(text.encode()).hexdigest()
        user["step"] = "confirm_password"
        send(chat, "Повторите пароль.")
        return
    if step == "confirm_password":
        if not hmac.compare_digest(hashlib.sha256(text.encode()).hexdigest(), user.pop("pending", "")):
            user["step"] = "set_password"
            send(chat, "Пароли не совпали. Поставьте пароль заново.")
            return
        user["salt"] = secrets.token_hex(16)
        user["hash"] = password_hash(text, user["salt"])
        user["session"] = now + SESSION_SECONDS
        user["step"] = "menu"
        send(chat, "✅ Пароль установлен.")
        menu(chat)
        return
    if user.get("session", 0) < now and step != "password":
        user["step"] = "password"
        send(chat, "🔑 Введите пароль.")
        return
    if step == "password":
        if hmac.compare_digest(password_hash(text, user["salt"]), user["hash"]):
            user["attempts"] = 0
            user["session"] = now + SESSION_SECONDS
            user["step"] = "menu"
            menu(chat)
        else:
            user["attempts"] = user.get("attempts", 0) + 1
            if user["attempts"] >= MAX_ATTEMPTS:
                user["attempts"] = 0
                user["locked_until"] = now + LOCK_SECONDS
                user["step"] = "password"
                send(chat, "🔒 Неверный пароль 5 раз подряд. Бот заблокирован для вас на 15 минут.")
                log("locked", sender)
            else:
                send(chat, f"Неверный пароль. Осталось попыток: {MAX_ATTEMPTS - user['attempts']}.")
        return

    user["session"] = now + SESSION_SECONDS
    if step in ("grant_id", "revoke_id"):
        target = text.lstrip("@")
        if not target.isdigit():
            send(chat, "Нужен числовой Telegram ID пользователя, например 123456789.")
            return
        if step == "revoke_id":
            registry = load_registry()
            before = len(registry["entries"])
            registry["entries"] = [entry for entry in registry["entries"] if entry["id"] != target]
            if len(registry["entries"]) == before:
                send(chat, f"У {target} нет надписи.")
            else:
                publish(registry, f"Verified registry: revoke {target}")
                send(chat, f"❌ Надпись у {target} забрана. Клиенты AyuGram обновят список в течение часа.")
                log("revoke", target, "by", sender)
            user["step"] = "menu"
            menu(chat)
            return
        user["target"] = target
        user["step"] = "grant_text"
        send(chat, "Если хотите, введите кастомный бейдж — например «Этот аккаунт самого крутого спонсора».\n\nИли нажмите «Продолжить», чтобы выбрать один из классических вариантов.",
             [("➡️ Продолжить", "classic")])
        return
    if step == "grant_text":
        if not text or len(text) > 120:
            send(chat, "Текст должен быть от 1 до 120 символов.")
            return
        grant(state, chat, sender, user, "custom", text)
        return
    menu(chat)


def grant(state, chat, sender, user, kind, text):
    target = user.pop("target", None)
    if not target:
        menu(chat)
        return
    registry = load_registry()
    registry["entries"] = [entry for entry in registry["entries"] if entry["id"] != target]
    registry["entries"].append({"id": target, "kind": kind, "text": text, "by": str(sender), "at": int(time.time())})
    publish(registry, f"Verified registry: grant {target}")
    send(chat, f"✅ {target}: «{text}»\n\nНадпись увидят все пользователи AyuGram для iOS в течение часа.")
    log("grant", target, kind, "by", sender)
    user["step"] = "menu"
    menu(chat)


def handle_callback(state, query):
    sender = query.get("from", {}).get("id")
    chat = query.get("message", {}).get("chat", {}).get("id")
    call("answerCallbackQuery", callback_query_id=query["id"])
    if sender not in TEAM or chat is None:
        return
    user = state["users"].setdefault(str(sender), {"step": "new"})
    if "hash" not in user or user.get("session", 0) < time.time() or user.get("locked_until", 0) > time.time():
        user["step"] = "password" if "hash" in user else "new"
        send(chat, "🔑 Введите пароль." if "hash" in user else "Сначала поставьте пароль: /start")
        return
    data = query.get("data")
    user["session"] = time.time() + SESSION_SECONDS
    if data == "grant":
        user["step"] = "grant_id"
        send(chat, "Отправьте Telegram ID пользователя, которому выдать надпись.")
    elif data == "revoke":
        user["step"] = "revoke_id"
        send(chat, "Отправьте Telegram ID пользователя, у которого забрать надпись.")
    elif data == "list":
        entries = load_registry()["entries"]
        lines = [f"{entry['id']} — {entry['text']}" for entry in entries]
        send(chat, "\n".join(lines) if lines else "Список пуст.")
        menu(chat)
    elif data == "logout":
        user["session"] = 0
        user["step"] = "password"
        send(chat, "🔒 Вы вышли. Чтобы продолжить, введите пароль.")
    elif data == "classic":
        if user.get("step") != "grant_text":
            menu(chat)
            return
        user["step"] = "grant_classic"
        send(chat, "Выберите надпись:", [(CLASSIC["sponsor"], "c:sponsor"), (CLASSIC["developer"], "c:developer"), (CLASSIC["plugins"], "c:plugins")])
    elif data and data.startswith("c:") and user.get("step") == "grant_classic":
        kind = data[2:]
        if kind in CLASSIC:
            grant(state, chat, sender, user, kind, CLASSIC[kind])


def main():
    if not (CONFIG / "registry-key.pem").is_file():
        sys.exit("registry-key.pem is missing")
    state = load_state()
    offset = state.get("offset", 0)
    log("started")
    while True:
        updates = call("getUpdates", offset=offset, timeout=50, allowed_updates=["message", "callback_query"]) or []
        for update in updates:
            offset = update["update_id"] + 1
            try:
                if "message" in update:
                    handle_message(state, update["message"])
                elif "callback_query" in update:
                    handle_callback(state, update["callback_query"])
            except Exception as error:  # one bad update must not stop the bot
                log("error", repr(error))
                chat = (update.get("message") or update.get("callback_query", {}).get("message") or {}).get("chat", {}).get("id")
                if chat:
                    send(chat, "⚠️ Ошибка. Попробуйте ещё раз.")
            state["offset"] = offset
            save_state(state)


if __name__ == "__main__":
    main()
