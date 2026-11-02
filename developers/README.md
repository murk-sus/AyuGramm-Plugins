# Plugin developers

`ID` lists the Telegram IDs that may build plugins in the cloud from AyuGram for iOS
(Settings → AyuGram → Tools → Cloud build). Anyone else builds on their own computer with the SDKs.

How a cloud build works:

1. In AyuGram the developer signs in with a GitHub token that can write to this repository
   (a fine-grained token limited to `murk-sus/AyuGramm-Plugins`, permission *Contents: read and write*).
   Only collaborators of this repository can push, so the token is the real gate.
2. AyuGram checks that the account's Telegram ID is in `ID`, then commits the source to the
   `beta` branch under `beta-src/<telegram id>/<file>` in the developer's own name.
3. `.github/workflows/beta-compile.yml` checks the ID again, checks `github.json` when the
   developer's GitHub login is mapped there, and builds the file:

   | Source | Build |
   | --- | --- |
   | `.js` | syntax check |
   | `.ts` | TypeScript → JavaScript (esbuild) |
   | `.py` | syntax check |
   | `.rs` | Rust → WebAssembly with `sdk/rust` |
   | `.as.ts` | AssemblyScript → WebAssembly with `sdk/assemblyscript` |
   | `.zig` | Zig → WebAssembly with `sdk/zig` |
   | `.go` | TinyGo → WebAssembly with `sdk/tinygo` |

   WebAssembly sources take their manifest from the first line (`// @manifest {...}`) or from
   `<name>.manifest.json` next to them.
4. The result lands in `beta-out/<telegram id>/` with a `.status.json`; AyuGram downloads it and
   installs it on the developer's device only. Beta builds are unsigned, so plugins that inject
   into the app need developer mode.

To add a developer: append the Telegram ID to `ID`, add the GitHub login to `github.json`, and
invite the login as a collaborator with write access.
