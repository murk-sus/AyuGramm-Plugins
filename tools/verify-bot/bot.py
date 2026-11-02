#!/usr/bin/env python3
"""@ayugram_dev_settings_bot: AyuGram for iOS team bot.

Only the team's Telegram IDs may use it; everyone else is refused. Each team member sets a
password (typed twice) and enters it to unlock the bot. Then they can grant or revoke the
"verified by the AyuGram for iOS team" label for a Telegram user, with a custom text or one of
the classic ones, and add fonts and plugins to the catalog: send the file, name its author
(their Telegram @nick) and a description, and the bot commits it to github.com/murk-sus/AyuGramm-Plugins.
The Catalog workflow there rebuilds index.json, fonts/index.json and the README; the bot reports
when it has finished. Plugins can be signed as official with the AyuGram plugin key.

The list lives in registry/verified.json of github.com/murk-sus/AyuGramm-Plugins, signed with
Ed25519 (registry/verified.json.sig). Every AyuGram client downloads it, checks the signature
with the public key built into the app and shows the label.

Secrets stay on this machine, never in the repository:
  ~/.config/ayugram-bot/token             the bot token
  ~/.config/ayugram-bot/registry-key.pem  the registry signing key
  ~/.config/ayugram-bot/state.json        password hashes and conversation state
  ~/.config/ayugram-plugins/signing-key.pem  the plugin signing key ($AYU_SIGNING_KEY), optional
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
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog  # noqa: E402

TEAM = {7556953433, 7864640050, 7754143736, 8276132300}
CONFIG = Path(os.environ.get("AYU_BOT_CONFIG", Path.home() / ".config/ayugram-bot"))
REPO = "murk-sus/AyuGramm-Plugins"
REGISTRY_PATH = "registry/verified.json"
GH = os.environ.get("AYU_BOT_GH", str(Path.home() / ".local/bin/gh"))
SESSION_SECONDS = 30 * 60
MAX_ATTEMPTS = 5
LOCK_SECONDS = 15 * 60
PLUGIN_KEY = Path(os.environ.get("AYU_SIGNING_KEY", Path.home() / ".config/ayugram-plugins/signing-key.pem"))
DOWNLOAD_LIMIT = 20 * 1024 * 1024  # the Bot API serves files up to 20 MB
KIND_TITLES = {"font": "Шрифт", "js": "Плагин JavaScript", "python": "Плагин Python", "lua": "Плагин Lua",
               "wasm": "Плагин Rust (WebAssembly)", "iosplug": "Нативный плагин (.iosplug)"}

CLASSIC = {
    "sponsor": "Этот пользователь спонсирует AyuGram",
    "developer": "Этот человек является разработчиком AyuGram",
    "plugins": "Этот человек официально подтверждён как создатель плагинов для AyuGram",
}

def log(*parts):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), *parts, flush=True)


# MARK: Telegram

def call(method, **params):
    token = (CONFIG / "token").read_text().strip()
    api = f"https://api.telegram.org/bot{token}/"
    data = urllib.parse.urlencode({key: json.dumps(value) if isinstance(value, (dict, list)) else value for key, value in params.items()}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(api + method, data=data), timeout=70) as response:
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


def api(method, path, body=None):
    request = urllib.request.Request(f"https://api.github.com/repos/{REPO}/{path}", method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": "Bearer " + gh_token(), "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())


def folder_files(folder):
    """Paths of the files in a repository folder on main."""
    listing = github("GET", folder + "?ref=main")
    if not isinstance(listing, list):
        return []
    return [entry["path"] for entry in listing if entry.get("type") == "file"]


def read_json(path, default):
    current = github("GET", path + "?ref=main")
    return json.loads(base64.b64decode(current["content"])) if current else default


def commit(files, message):
    """Writes (bytes) and deletes (None) several files in one commit on main; returns its sha."""
    for attempt in range(3):
        head = api("GET", "git/ref/heads/main")["object"]["sha"]
        base_tree = api("GET", f"git/commits/{head}")["tree"]["sha"]
        tree = []
        for path, content in sorted(files.items()):
            if content is None:
                tree.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
            else:
                blob = api("POST", "git/blobs", {"content": base64.b64encode(content).decode(), "encoding": "base64"})
                tree.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        new_tree = api("POST", "git/trees", {"base_tree": base_tree, "tree": tree})["sha"]
        new_commit = api("POST", "git/commits", {"message": message, "tree": new_tree, "parents": [head]})["sha"]
        try:
            api("PATCH", "git/refs/heads/main", {"sha": new_commit})
            return new_commit
        except urllib.error.HTTPError as error:
            # main moved meanwhile (the index workflow commits too): start over from the new head.
            if error.code != 422 or attempt == 2:
                raise
    return None


def catalog_run(sha):
    """Conclusion of the Catalog workflow for a commit: None while it is pending."""
    runs = api("GET", f"actions/runs?head_sha={sha}&per_page=20").get("workflow_runs", [])
    for run in runs:
        if run.get("name") == "Catalog":
            return run.get("conclusion") if run.get("status") == "completed" else None
    return None


def report_when_built(chat, sha, title):
    """Tells the team member whether the catalog accepted the commit (runs in a thread)."""
    def wait():
        for _ in range(40):
            time.sleep(15)
            try:
                result = catalog_run(sha)
            except Exception as error:  # network trouble: keep waiting
                log("catalog run check", repr(error))
                continue
            if result == "success":
                send(chat, f"✅ {title} уже в каталоге. Приложение увидит изменения при следующем открытии каталога.")
                return
            if result is not None:
                send(chat, f"⚠️ Каталог не пересобрался ({result}) после «{title}». Смотрите Actions в github.com/{REPO}.")
                return
        send(chat, f"⏳ Сборка каталога после «{title}» идёт дольше 10 минут. Проверьте Actions в github.com/{REPO}.")
    threading.Thread(target=wait, daemon=True).start()


def download(file_id):
    """Bytes of a Telegram file sent to the bot."""
    info = call("getFile", file_id=file_id)
    if not info or "file_path" not in info:
        return None
    token = (CONFIG / "token").read_text().strip()
    with urllib.request.urlopen(f"https://api.telegram.org/file/bot{token}/{info['file_path']}", timeout=120) as response:
        return response.read(DOWNLOAD_LIMIT + 1)


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
    send(chat, "Что сделать?", [("✅ Выдать надпись", "grant"), ("❌ Забрать надпись", "revoke"), ("🖼 Баннер профиля", "banner"), ("📋 Список", "list"),
                                ("📦 Добавить шрифт или плагин", "upload"), ("🗂 Каталог", "catalog"), ("🗑 Убрать из каталога", "remove"),
                                ("🔒 Выйти", "logout")])


# MARK: Catalog uploads

UPLOADS = Path(os.environ.get("AYU_BOT_UPLOADS", CONFIG / "uploads"))


def save_upload(sender, item):
    """Keeps the uploaded file outside state.json between conversation steps."""
    UPLOADS.mkdir(parents=True, exist_ok=True)
    os.chmod(UPLOADS, 0o700)
    path = UPLOADS / f"{sender}.bin"
    path.write_bytes(item.data)
    return {"kind": item.kind, "id": item.id, "name": item.name, "version": item.version, "description": item.description,
            "filename": item.filename, "injects": item.injects, "sha256": item.sha256}


def load_upload(sender, upload):
    path = UPLOADS / f"{sender}.bin"
    if not upload or not path.is_file():
        return None
    data = path.read_bytes()
    if catalog.hashlib.sha256(data).hexdigest() != upload["sha256"]:
        return None
    return catalog.Item(kind=upload["kind"], id=upload["id"], name=upload["name"], version=upload.get("version", ""),
                        description=upload.get("description", ""), filename=upload["filename"], data=data,
                        injects=upload.get("injects", False))


def drop_upload(sender, user):
    user.pop("upload", None)
    try:
        (UPLOADS / f"{sender}.bin").unlink()
    except FileNotFoundError:
        pass


def receive_file(chat, sender, user, document):
    name = document.get("file_name") or "file"
    if (document.get("file_size") or 0) > DOWNLOAD_LIMIT:
        send(chat, "Файл больше 20 МБ: Telegram не отдаёт ботам такие файлы.")
        return
    data = download(document["file_id"])
    if data is None or len(data) > DOWNLOAD_LIMIT:
        send(chat, "Не удалось скачать файл. Пришлите ещё раз.")
        return
    try:
        item = catalog.inspect(name, data)
    except catalog.Refused as reason:
        send(chat, f"⛔ {reason}\n\nПришлите другой файл или /cancel.")
        return
    existing = folder_files(item.folder)
    user["upload"] = save_upload(sender, item)
    user["upload"]["update"] = bool(existing)
    user["step"] = "upload_author"
    what = KIND_TITLES.get(item.kind, item.kind)
    details = f"{what}: {item.name}" + (f" {item.version}" if item.version else "") + f"\nid: {item.id}"
    if existing:
        details += "\n\n♻️ Такой уже есть в каталоге — он будет заменён."
    if item.injects:
        details += "\n\n⚠️ Плагин встраивается в приложение (@inject). Без подписи его можно поставить только через безопасную зону."
    send(chat, details + "\n\nКто автор? Отправьте ник в Telegram, например @lwwlt.")


def ask_description(chat, user):
    upload = user["upload"]
    current = upload.get("description", "")
    user["step"] = "upload_description"
    hint = f"\n\nСейчас: «{current}». Отправьте «-», чтобы оставить." if current else ""
    send(chat, "Описание одной строкой (до 300 символов): что это и чем хорош." + hint)


def confirm_upload(chat, user):
    upload = user["upload"]
    lines = [f"{KIND_TITLES.get(upload['kind'], upload['kind'])}: {upload['name']}" + (f" {upload['version']}" if upload.get("version") else ""),
             f"id: {upload['id']}", f"Автор: {upload['author']}", f"Описание: {upload['description'] or '—'}"]
    if upload["kind"] != "font":
        lines.append("Подпись: " + ("официальный (подписан ключом AyuGram)" if upload.get("sign") else "без подписи"))
    user["step"] = "upload_confirm"
    send(chat, "\n".join(lines) + "\n\nОпубликовать?", [("✅ Опубликовать", "u:publish"), ("✖️ Отмена", "u:cancel")])


def publish_upload(chat, sender, user):
    upload = user.get("upload")
    item = load_upload(sender, upload)
    if item is None:
        drop_upload(sender, user)
        user["step"] = "menu"
        send(chat, "Файл потерялся. Начните заново.")
        menu(chat)
        return
    existing = folder_files(item.folder)
    signature = None
    signatures = None
    if not item.is_font:
        signatures = read_json("signatures.json", {})
        if upload.get("sign"):
            signature = catalog.sign(item.data, PLUGIN_KEY)
    files = catalog.changes(item, upload["author"], upload["description"], existing, signatures, signature, by=sender)
    verb = "update" if existing else "add"
    noun = "font" if item.is_font else "plugin"
    sha = commit(files, f"Catalog: {verb} {noun} {item.name} by {upload['author']}")
    title = f"{item.name} ({upload['author']})"
    log("catalog", verb, noun, item.id, "by", sender, sha)
    drop_upload(sender, user)
    user["step"] = "menu"
    send(chat, f"📤 {title}: отправлено в GitHub. Пересобираю каталог и README, сообщу, когда будет готово.")
    report_when_built(chat, sha, title)
    menu(chat)


def show_catalog(chat):
    plugins = read_json("index.json", {}).get("plugins", [])
    fonts = read_json("fonts/index.json", {}).get("fonts", [])
    lines = ["🔤 Шрифты:"] + [f"• {f['name']} — {f.get('author') or '—'} (id {f['id']})" for f in fonts] or ["—"]
    lines += ["", "🧩 Плагины:"] + [f"• {p['name']} {p['version']} — {p['author']} (id {p['id']})" for p in plugins]
    text = "\n".join(lines)
    for start in range(0, len(text), 3900):
        send(chat, text[start:start + 3900])


def remove_item(chat, sender, user, text):
    parts = text.split()
    if len(parts) != 2 or parts[0] not in ("font", "plugin", "шрифт", "плагин") or not catalog.ID.match(parts[1]):
        send(chat, "Формат: «шрифт id» или «плагин id», например «шрифт slice-cut». /cancel — отмена.")
        return
    kind = "font" if parts[0] in ("font", "шрифт") else "plugin"
    folder = f"fonts/{parts[1]}" if kind == "font" else f"plugins/{parts[1]}"
    existing = folder_files(folder)
    if not existing:
        send(chat, "Такого нет в каталоге. /cancel — отмена.")
        return
    user["removal"] = {"kind": kind, "id": parts[1]}
    user["step"] = "remove_confirm"
    send(chat, f"Убрать {'шрифт' if kind == 'font' else 'плагин'} {parts[1]} из каталога? Файлы удалятся из репозитория.",
         [("🗑 Убрать", "r:yes"), ("✖️ Отмена", "r:no")])


def confirm_removal(chat, sender, user):
    removal = user.pop("removal", None)
    user["step"] = "menu"
    if not removal:
        menu(chat)
        return
    folder = f"fonts/{removal['id']}" if removal["kind"] == "font" else f"plugins/{removal['id']}"
    existing = folder_files(folder)
    if existing:
        signatures = read_json("signatures.json", {}) if removal["kind"] != "font" else None
        sha = commit(catalog.removal(removal["kind"], removal["id"], existing, signatures), f"Catalog: remove {removal['kind']} {removal['id']}")
        log("catalog remove", removal["kind"], removal["id"], "by", sender, sha)
        send(chat, f"🗑 {removal['id']}: удалено из репозитория. Пересобираю каталог.")
        report_when_built(chat, sha, removal["id"])
    menu(chat)


def valid_banner_url(value):
    if not value or len(value) > 512 or any(c.isspace() or ord(c) < 32 for c in value) or "\\" in value:
        return False
    try:
        url = urllib.parse.urlsplit(value)
        return (url.scheme == "https" and bool(url.hostname) and url.username is None
                and url.password is None and "#" not in value and (url.port is None or 1 <= url.port <= 65535))
    except ValueError:
        return False


def banner_target(value):
    if not value.isascii() or not value.isdecimal():
        return None
    number = int(value)
    return str(number) if 0 < number <= 2 ** 63 - 1 else None


def set_banner(chat, sender, user, value):
    target = user.get("target")
    if not target:
        user["step"] = "menu"
        menu(chat)
        return
    if value != "-" and not valid_banner_url(value):
        send(chat, "Нужна HTTPS-ссылка на изображение (до 512 символов, без логина и пароля), либо «-» для удаления. /cancel — отмена.")
        return
    registry = load_registry()
    entry = next((entry for entry in registry["entries"] if entry["id"] == target), None)
    if entry is None:
        send(chat, "Сначала выдайте этому пользователю надпись верификации.")
    else:
        if value == "-":
            entry.pop("banner", None)
        else:
            entry["banner"] = value
        publish(registry, f"Verified registry: {'remove' if value == '-' else 'set'} banner {target}")
        send(chat, f"✅ Баннер {target} {'удалён' if value == '-' else 'обновлён'}. Надпись сохранена. Клиенты обновят реестр в течение часа.")
        log("banner", target, "by", sender)
    user.pop("target", None)
    user["step"] = "menu"
    menu(chat)


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
    if text in ("/cancel", "/start"):
        user.pop("target", None)
        user.pop("removal", None)
        drop_upload(sender, user)
        user["step"] = "menu"
        menu(chat)
        return
    if message.get("document"):
        if step != "upload_file":
            send(chat, "Чтобы добавить файл в каталог, нажмите «📦 Добавить шрифт или плагин».")
            menu(chat)
            return
        receive_file(chat, sender, user, message["document"])
        return
    if step == "upload_file":
        send(chat, "Пришлите файл шрифта (.ttf/.otf) или плагина (.ayu.js, .ayu.py, .ayu.lua, .wasm, .iosplug) документом. /cancel — отмена.")
        return
    if step == "upload_author":
        author = text if text.startswith("@") else "@" + text
        if not catalog.NICK.match(author):
            send(chat, "Нужен ник в Telegram: @ и 4–32 символа (буквы, цифры, _). /cancel — отмена.")
            return
        user["upload"]["author"] = author
        ask_description(chat, user)
        return
    if step == "upload_description":
        if text != "-":
            if not text or len(text) > 300:
                send(chat, "Описание должно быть от 1 до 300 символов, или «-».")
                return
            user["upload"]["description"] = " ".join(text.split())
        if user["upload"]["kind"] == "font":
            confirm_upload(chat, user)
        elif PLUGIN_KEY.is_file():
            user["step"] = "upload_sign"
            send(chat, "Подписать плагин ключом AyuGram? Подписанный считается официальным и может встраиваться в приложение. "
                       "Подписывайте только код, который прочитали.", [("✍️ Подписать", "u:sign"), ("Без подписи", "u:nosign")])
        else:
            confirm_upload(chat, user)
        return
    if step == "remove_id":
        remove_item(chat, sender, user, text)
        return
    if text.split(maxsplit=1)[:1] == ["/banner"]:
        parts = text.split(maxsplit=2)
        if len(parts) != 3 or banner_target(parts[1]) is None:
            send(chat, "Использование: /banner ID https://example.com/banner.png\nУдалить: /banner ID -")
            return
        user["target"] = banner_target(parts[1])
        user["step"] = "banner_url"
        set_banner(chat, sender, user, parts[2])
        return
    if step == "banner_id":
        target = banner_target(text)
        if target is None:
            send(chat, "Нужен положительный числовой Telegram ID. /cancel — отмена.")
            return
        user["target"] = target
        user["step"] = "banner_url"
        send(chat, "Отправьте HTTPS-ссылку на баннер. «-» — удалить баннер, /cancel — отмена.")
        return
    if step == "banner_url":
        set_banner(chat, sender, user, text)
        return
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
    target = user.get("target")
    if not target:
        menu(chat)
        return
    registry = load_registry()
    previous = next((entry for entry in registry["entries"] if entry["id"] == target), {})
    registry["entries"] = [entry for entry in registry["entries"] if entry["id"] != target]
    entry = {"id": target, "kind": kind, "text": text, "by": str(sender), "at": int(time.time())}
    if previous.get("banner"):
        entry["banner"] = previous["banner"]
    registry["entries"].append(entry)
    publish(registry, f"Verified registry: grant {target}")
    user.pop("target", None)
    send(chat, f"✅ {target}: «{text}»\n\nНадпись увидят все пользователи AyuGram для iOS в течение часа.")
    log("grant", target, kind, "by", sender)
    user["step"] = "menu"
    menu(chat)


def handle_callback(state, query):
    sender = query.get("from", {}).get("id")
    chat = query.get("message", {}).get("chat", {}).get("id")
    call("answerCallbackQuery", callback_query_id=query["id"])
    if sender not in TEAM or chat is None or query.get("message", {}).get("chat", {}).get("type") != "private":
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
    elif data == "banner":
        user.pop("target", None)
        user["step"] = "banner_id"
        send(chat, "Отправьте Telegram ID верифицированного пользователя. /cancel — отмена.")
    elif data == "list":
        entries = load_registry()["entries"]
        lines = [f"{entry['id']} — {entry['text']}" for entry in entries]
        send(chat, "\n".join(lines) if lines else "Список пуст.")
        menu(chat)
    elif data == "upload":
        drop_upload(sender, user)
        user["step"] = "upload_file"
        send(chat, "Пришлите файл документом: шрифт .ttf/.otf или плагин .ayu.js, .ayu.py, .ayu.lua, .wasm, .iosplug. /cancel — отмена.")
    elif data == "catalog":
        show_catalog(chat)
        menu(chat)
    elif data == "remove":
        user["step"] = "remove_id"
        send(chat, "Что убрать? Напишите «шрифт id» или «плагин id» (id есть в «🗂 Каталог»). /cancel — отмена.")
    elif data in ("u:sign", "u:nosign") and user.get("step") == "upload_sign" and user.get("upload"):
        user["upload"]["sign"] = data == "u:sign"
        confirm_upload(chat, user)
    elif data == "u:publish" and user.get("step") == "upload_confirm":
        publish_upload(chat, sender, user)
    elif data == "u:cancel":
        drop_upload(sender, user)
        user["step"] = "menu"
        send(chat, "Отменено.")
        menu(chat)
    elif data == "r:yes" and user.get("step") == "remove_confirm":
        confirm_removal(chat, sender, user)
    elif data == "r:no":
        user.pop("removal", None)
        user["step"] = "menu"
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
