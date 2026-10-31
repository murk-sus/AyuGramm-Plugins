# AyuGramm Plugins

The plugin library for [AyuGramm-IOS](https://github.com/dsn2fvhmn4-lgtm/AyuGramm-IOS).
AyuGram downloads [`index.json`](index.json) from this repository and lists every plugin under
**Settings → AyuGram → Plugins → bag icon (Catalog)**.

## Code plugins (JavaScript)

| Plugin | Author | Version | What it does |
|---|---|---|---|
| [Clean links](plugins/clean-links/plugin.ayu.js) | murk-sus & dsn2fvhmn4-lgtm | 1.0 | Removes tracking parameters (utm_*, fbclid, gclid, si, igsh…) from links you send, so they do not reveal where you found them |
| [Layout fix](plugins/layout-fix/plugin.ayu.js) | murk-sus & dsn2fvhmn4-lgtm | 1.0 | Fixes text typed in the wrong keyboard layout: "ghbdtn" → "привет", "руддщ" → "hello" |
| [Minimal UI](plugins/minimal-ui/plugin.ayu.js) | murk-sus & dsn2fvhmn4-lgtm | 1.0 | A calmer Telegram: hides stories, similar channels, Premium statuses, the greeting sticker and the fast-share button while enabled |
| [Smart quotes](plugins/smart-quotes/plugin.ayu.js) | murk-sus & dsn2fvhmn4-lgtm | 1.1 | Straight quotes become «ёлочки» in Russian text and “curly” quotes otherwise; "--" becomes an em dash |
| [Text shortcuts](plugins/text-shortcuts/plugin.ayu.js) | murk-sus & dsn2fvhmn4-lgtm | 1.0 | Expands shortcuts in outgoing messages: :shrug: → ¯\_(ツ)_/¯, :lenny: → ( ͡° ͜ʖ ͡°), :tableflip: → (╯°□°)╯︵ ┻━┻, ->, <-, (c), (tm) and more |

## Python plugins

| Plugin | Author | Version | What it does |
|---|---|---|---|
| [Lyrics cleaner](plugins/lyrics-cleaner/plugin.ayu.py) | murk-sus & dsn2fvhmn4-lgtm | 1.0 | Removes "[Verse 1]", "Chorus:", "(x2)" and similar labels from song lyrics; switches in Settings → AyuGram → Lyrics sources. **inject** |

## Rust plugins (WebAssembly)

| Plugin | Author | Version | What it does |
|---|---|---|---|
| [Emoji shortcuts](plugins/emoji-shortcuts-rs/plugin.wasm) ([source](plugins-src/emoji-shortcuts-rs)) | murk-sus & dsn2fvhmn4-lgtm | 1.0 | `:fire:`, `:heart:`, `:ok:`, `:100:` and other shortcuts become emoji in messages you send |

## Native plugins (`.iosplug`)

Cards for the plugins built into AyuGram. Installing one switches the native adapter on; the
card itself contains no code.

| Plugin | Author | Version | What it does |
|---|---|---|---|
| [Album Cover Downloader](plugins/acd/plugin.iosplug) | murk-sus & dsn2fvhmn4-lgtm | 1.0 | Saves the available cover preview of an audio file to Photos |
| [Camera Flip](plugins/camera_flip/plugin.iosplug) | murk-sus & dsn2fvhmn4-lgtm | 0.2.0-ios.1 | Switch the round-video camera using vertical swipes or double taps |
| [Chat Colors](plugins/chat_colors/plugin.iosplug) | murk-sus & dsn2fvhmn4-lgtm | 1.0-ios.1 | Per-chat colors in the chat list, nine presets, custom HEX, brightness, colored-chat management and reset |
| [Delete My Messages](plugins/del_my_msgs/plugin.iosplug) | murk-sus & dsn2fvhmn4-lgtm | 1.0 | Finds and deletes your own messages in a chat after confirmation |
| [formatted copy](plugins/formatted_copy/plugin.iosplug) | murk-sus & dsn2fvhmn4-lgtm | 1.0.0-ios.1 | Native message copying with author, optional date/time, media labels and available reply quotes |
| [Arcade Games](plugins/game_arcade/plugin.iosplug) | murk-sus & dsn2fvhmn4-lgtm | 1.1 | 2048, Flappy Bird and Chrome Dino through the existing native Arcade Games bridge |
| [Group Mentions](plugins/group_mentions/plugin.iosplug) | murk-sus & dsn2fvhmn4-lgtm | 1.2-ios.1 | Native saved username groups with whole-command expansion and a per-chat cooldown |
| [HideAttachButtons](plugins/hide_attach_buttons/plugin.iosplug) | murk-sus & dsn2fvhmn4-lgtm | 1.0 | Hides the chosen sections of the attachment menu |
| [Mini Avatar](plugins/mini_avatar/plugin.iosplug) | murk-sus & dsn2fvhmn4-lgtm | 1.0 | Size of the avatars next to messages: 18–34 points |
| [petpet](plugins/petpet/plugin.iosplug) | murk-sus & dsn2fvhmn4-lgtm | 1.0.6-ios.1 | Native petpet GIF composition from a chat avatar or an image in Files, with preview and configurable resolution/frame delay |
| [Pill Labels](plugins/pill_labels/plugin.iosplug) | murk-sus & dsn2fvhmn4-lgtm | 1.0 | Outline and background for profile field labels, six colors |
| [Reactions Total](plugins/reactions_total/plugin.iosplug) | murk-sus & dsn2fvhmn4-lgtm | 2.0.0-ios.1 | Reaction totals in the message timestamp line, with compact counts, paid-reaction and channel filters |
| [Search+ for iOS](plugins/search_plus/plugin.iosplug) | murk-sus & dsn2fvhmn4-lgtm | 2.6.1-ios.2 | Multi-term search in the current chat/topic |
| [Service Cleaner](plugins/service_cleaner/plugin.iosplug) | murk-sus & dsn2fvhmn4-lgtm | 1.0 | Deletes loaded service messages after confirmation |
| [Auto Archive Chats](plugins/smart_auto_archiver/plugin.iosplug) | murk-sus & dsn2fvhmn4-lgtm | 1.0 | Archives inactive chats when the app starts |
| [Unlim Accounts](plugins/unlim_accounts/plugin.iosplug) | murk-sus & dsn2fvhmn4-lgtm | 1.0 | Raises the local client add-account limit to 999 through the existing iOS bridge |

## Installing

In the app: **Plugins → bag icon** → pick a plugin → **Install** (or **Update** when the catalog
has a newer version). The app shows the author, description and a warning first, and checks the
download against the SHA-256 in the index.

Manually: download `plugin.ayu.js` or `plugin.iosplug` and open it with **Plugins → +**.

## Writing a code plugin

Each code plugin is one file, `plugins/<id>/plugin.ayu.js`, with a header:

```js
// ==AyuPlugin==
// @id my-plugin
// @name My plugin
// @author your-github-name
// @version 1.0
// @description What it does.
// @tags text, privacy
// ==/AyuPlugin==

ayu.hooks.before(ayu.hooks.points.outgoingText, (text, ctx) => text.trim());
```

The full API is in the [AyuGramm-IOS docs](https://github.com/dsn2fvhmn4-lgtm/AyuGramm-IOS/blob/main/docs/CODE_PLUGINS.md):
intercepting and replacing outgoing text, switching features off, events, storage, toasts and timers.

## Python plugins

One file, `plugins/<id>/plugin.ayu.py`, with the same header as `#` comments. The `ayu` object
is already there:

```python
# ==AyuPlugin==
# @id my-plugin
# @name My plugin
# @author your-github-name
# @version 1.0
# @description What it does.
# ==/AyuPlugin==

@ayu.hooks.before(ayu.hooks.points.outgoing_text)
def trim(text, ctx):
    return text.strip()
```

The interpreter is [PocketPy](https://github.com/pocketpy/pocketpy) (a Python 3 subset) without
`os`, `io`, files or file imports. `str.lower()`/`upper()` only fold Latin letters.

## Rust plugins

Use the dependency-free SDK in [`sdk/rust`](sdk/rust) and build a `cdylib` for WebAssembly:

```sh
cargo build --release --target wasm32-unknown-unknown
cp target/wasm32-unknown-unknown/release/my_plugin.wasm plugins/my-plugin/plugin.wasm
```

The plugin describes itself with `ayugram_plugin::manifest!(br#"{...}"#)` and registers hooks in
`#[no_mangle] pub extern "C" fn ayu_init()`. See [`plugins-src/emoji-shortcuts-rs`](plugins-src/emoji-shortcuts-rs).

## Safe zone: injecting plugins

Ordinary plugins (outgoing text, switching features off, storage, toasts, settings) may come from
anywhere. Plugins that **inject** into the app — `ayu.player` and the `lyrics.text` hook — declare
`@inject true` (`"inject": true` in a Rust manifest) and are installed only when signed by
AyuGram: every plugin here is signed (`signatures.json`, Ed25519) after review. An unsigned
injecting plugin installs only when the user enables *Injecting plugins from unofficial sources*
in the developer settings and accepts that the responsibility is entirely theirs.

After a pull request is merged the maintainer re-signs: `python3 tools/sign.py && python3 tools/build_index.py`.

## Submitting a plugin

1. Copy [`template/plugin.ayu.js`](template/plugin.ayu.js) to `plugins/<your-id>/plugin.ayu.js`
   (or put a native card at `plugins/<id>/plugin.iosplug`).
2. The id must equal the folder name (`a-z`, `0-9`, `-`, `_`).
3. Check locally:
   ```sh
   node tools/test_plugins.js
   python3 tools/build_index.py
   ```
4. Open a pull request. After the merge a GitHub Action rebuilds `index.json`.

Rules: local work only, no data collection; a plugin must do what its description says.

## Security

Code plugins run as code, but each in its own sandbox: JavaScriptCore, PocketPy or the WAMR WebAssembly interpreter. They have **no access
to the network, the account, files or sending messages**: only the text passed to their hooks and
their own storage. A plugin that does not answer in time is switched off automatically.
Install only what you trust, and read the code — it is short.

## Credits

All plugins in this catalog, the AyuGramm-IOS client and this repository are made by
**[murk-sus](https://github.com/murk-sus)** (Telegram [@asuka4scape_developer](https://t.me/asuka4scape_developer))
and **[dsn2fvhmn4-lgtm](https://github.com/dsn2fvhmn4-lgtm)** (Telegram [@neosay](https://t.me/neosay)), together.
