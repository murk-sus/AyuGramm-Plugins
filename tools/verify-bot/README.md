# Team bot (@ayugram_dev_settings_bot)

Only the team's Telegram IDs can use it, with the same password sessions for everything. It
edits and signs `registry/verified.json` and adds fonts and plugins to the catalog.
Secrets remain under `~/.config/ayugram-bot` (and the plugin key under
`~/.config/ayugram-plugins`); never copy them into the repository.

## Access

Only the owner (`OWNER` in `bot.py`, 8276132300) sees **👥 Доступ** and can add or remove the
Telegram IDs allowed to use the bot; the action itself re-checks the sender. The list is
`~/.config/ayugram-bot/team.json`; without it the built-in `TEAM` applies, and the owner is
always in it. A removed ID loses its password, session and unfinished upload at once; an added
one writes /start to the bot and sets a password.

## Fonts and plugins

**📦 Добавить шрифт или плагин** → send the file as a document → the author's Telegram @nick →
a description (`-` keeps the plugin's own) → for plugins, sign or not → a screenshot (photo or
PNG/JPG/WEBP up to 5 MB; fonts without one get a drawn preview) → **Опубликовать**.

- Fonts: `.ttf` / `.otf` up to 15 MB with a PostScript name; stored as `fonts/<id>/font.ttf`
  and `font.json`.
- Plugins: JavaScript (`.ayujs`, `.ayu.js`, `.js`), Python (`.ayupy`, `.ayu.py`, `.py`),
  Lua (`.ayulua`, `.ayu.lua`, `.lua`), Rust (`.wasm`, `.ayuwasm`) and `.iosplug`, checked with
  the rules of `tools/build_index.py`; stored as `plugins/<id>/plugin.*` and `meta.json`
  (author, description, official).
- Every item has its own folder: the file, `screenshot.png|jpg|webp` and a `README.md` the
  Catalog workflow writes from the catalog (author, version, description, screenshot, SHA-256).
- Signing uses `$AYU_SIGNING_KEY` or `~/.config/ayugram-plugins/signing-key.pem` and makes the
  plugin official, so it may inject into the app. Sign only code you have read.
- Sending an item that already exists replaces it. **🗑 Убрать из каталога** deletes one
  (`шрифт <id>` or `плагин <id>`), **🗂 Каталог** lists everything.

Each change is one commit on `main`. The Catalog workflow rebuilds `index.json`,
`fonts/index.json` and the generated part of `README.md`; the bot reports when it is done.

## Verification labels

For an already verified user:

```text
/banner 123456789 https://example.com/banner.png
/banner 123456789 -
```

The second command removes only the banner. Changing the verification label keeps the banner.
The “Баннер профиля” button provides the same flow; `/cancel` cancels it.
Links must use HTTPS, have at most 512 characters and contain no credentials or fragment.
Clients refresh the signed registry within an hour. The iOS client caps downloads at 4 MiB.

## Tests and deployment

Local tests use mocked Telegram/GitHub calls and never read tokens or signing keys:

```sh
python3 -m unittest discover -s tools/verify-bot -p 'test_*.py'
```

Deploy `bot.py`, `catalog.py` and `../build_index.py` into one folder, then restart the bot
service. Running `bot.py` starts polling and sending messages; tests do not start it.
