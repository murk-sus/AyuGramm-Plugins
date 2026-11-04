# Font catalog

VoidGram shows these fonts in the **Fonts** section of the plugin catalog and under
**Settings → VoidGram → Appearance → Messages → Font catalog** (27.0: **WhiteGram → Font catalog**).
Choosing one downloads it, checks it against the SHA-256 in [`index.json`](index.json) and makes
it the app font (after a relaunch).

## Adding a font

The team adds fonts through @ayugram_dev_settings_bot: send the file, name the author's
Telegram @nick and a description. The bot commits `fonts/<id>/`, and the Catalog workflow
rebuilds `fonts/index.json` and the README.

By hand:

1. Create `fonts/<id>/` (`a-z`, `0-9`, `-`, `_`).
2. Put the font there as `font.ttf` or `font.otf` (up to 15 MB). It needs a PostScript name
   (name ID 6): iOS selects fonts by it.
3. Add `font.json`:
   ```json
   {"name": "My Font", "author": "@telegram_nick", "description": "One line about it"}
   ```
4. Optionally add `screenshot.png` (or `.jpg`, `.webp`) as a preview.
5. Run `python3 tools/build_fonts_index.py` and commit `fonts/index.json`, or open a pull
   request — the GitHub Action rebuilds the index after the merge.

Only add fonts whose author allows redistributing them (for example under the SIL Open Font License).
