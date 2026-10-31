# Font catalog

AyuGram shows these fonts under **Settings → AyuGram → WhiteGram → Font catalog**. Choosing
one downloads it, checks it against the SHA-256 in [`index.json`](index.json) and makes it the
app font (after a relaunch).

## Adding a font

1. Create `fonts/<id>/` (`a-z`, `0-9`, `-`, `_`).
2. Put the font there as `font.ttf` or `font.otf` (up to 15 MB).
3. Add `font.json`:
   ```json
   {"name": "My Font", "author": "who made it", "description": "One line about it"}
   ```
4. Run `python3 tools/build_fonts_index.py` and commit `fonts/index.json`, or open a pull
   request — the GitHub Action rebuilds the index after the merge.

Only add fonts whose licence allows redistribution (for example SIL Open Font License).
