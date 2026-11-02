#!/usr/bin/env node
// Builds plugin sources pushed to the `beta` branch (see developers/README.md).
// Usage: node compile.mjs --main <main checkout> --actor <github login> <beta-src/<id>/<file>>...
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const args = process.argv.slice(2);
const option = (name) => {
  const index = args.indexOf(name);
  if (index < 0) return null;
  const value = args[index + 1];
  args.splice(index, 2);
  return value;
};
const mainDir = path.resolve(option("--main") ?? ".");
const actor = (option("--actor") ?? "").toLowerCase();
const files = args.filter((file) => file.startsWith("beta-src/") && !file.endsWith(".manifest.json") && fs.existsSync(file));

const allowedIds = new Set(fs.readFileSync(path.join(mainDir, "developers/ID"), "utf8").split(/\s+/).filter(Boolean));
const logins = JSON.parse(fs.readFileSync(path.join(mainDir, "developers/github.json"), "utf8")).logins ?? {};
const loginOf = (id) => Object.entries(logins).find(([, value]) => String(value) === id)?.[0]?.toLowerCase() ?? null;

const run = (command, commandArgs, cwd) => execFileSync(command, commandArgs, { cwd, stdio: ["ignore", "pipe", "pipe"], timeout: 10 * 60 * 1000 }).toString();
const sha256 = (data) => createHash("sha256").update(data).digest("hex");

// --- WebAssembly manifest section (custom section "ayu.manifest") ---
function leb128(value) {
  const bytes = [];
  do {
    let byte = value & 0x7f;
    value >>>= 7;
    if (value !== 0) byte |= 0x80;
    bytes.push(byte);
  } while (value !== 0);
  return Buffer.from(bytes);
}
function addManifest(wasm, manifestJson) {
  JSON.parse(manifestJson); // must be valid JSON
  const name = Buffer.from("ayu.manifest");
  const payload = Buffer.concat([leb128(name.length), name, Buffer.from(manifestJson)]);
  return Buffer.concat([wasm, Buffer.from([0]), leb128(payload.length), payload]);
}
function manifestFor(file, source) {
  const first = source.split("\n", 1)[0];
  const match = first.match(/@manifest\s+(\{.*\})\s*$/);
  if (match) return match[1];
  const sidecar = file.replace(/(\.as)?\.[a-z]+$/, ".manifest.json");
  if (fs.existsSync(sidecar)) return fs.readFileSync(sidecar, "utf8").trim();
  throw new Error("WebAssembly sources need a manifest: `// @manifest {...}` on the first line or <name>.manifest.json");
}

function build(file) {
  const source = fs.readFileSync(file, "utf8");
  const base = path.basename(file);
  const work = fs.mkdtempSync(path.join(os.tmpdir(), "ayu-beta-"));
  if (base.endsWith(".js")) {
    run("node", ["--check", file]);
    return { name: base.replace(/\.js$/, "") + ".js", data: Buffer.from(source) };
  }
  if (base.endsWith(".py")) {
    run("python3", ["-m", "py_compile", file]);
    return { name: base, data: Buffer.from(source) };
  }
  if (base.endsWith(".as.ts")) {
    fs.copyFileSync(path.join(mainDir, "sdk/assemblyscript/assembly/ayu.ts"), path.join(work, "ayu.ts"));
    fs.writeFileSync(path.join(work, "plugin.ts"), source);
    run("npx", ["--yes", "-p", "assemblyscript@0.27.31", "asc", "plugin.ts", "-o", "plugin.wasm", "--runtime", "stub", "-O3z", "--noAssert", "--use", "abort="], work);
    return { name: base.replace(/\.as\.ts$/, ".wasm"), data: addManifest(fs.readFileSync(path.join(work, "plugin.wasm")), manifestFor(file, source)) };
  }
  if (base.endsWith(".ts")) {
    const out = run("npx", ["--yes", "esbuild@0.24.0", file, "--format=iife", "--target=es2020", "--legal-comments=inline"]);
    // Keep the plugin header comments (esbuild keeps leading comments with --legal-comments=inline only for /*! */).
    const header = source.split("\n").filter((line) => line.trim().startsWith("// @")).join("\n");
    return { name: base.replace(/\.ts$/, ".js"), data: Buffer.from((header ? header + "\n" : "") + out) };
  }
  if (base.endsWith(".rs")) {
    fs.mkdirSync(path.join(work, "src"));
    fs.writeFileSync(path.join(work, "src/lib.rs"), source);
    fs.writeFileSync(path.join(work, "Cargo.toml"), `[package]\nname = "beta_plugin"\nversion = "0.1.0"\nedition = "2021"\n\n[lib]\ncrate-type = ["cdylib"]\n\n[dependencies]\nayugram-plugin = { path = ${JSON.stringify(path.join(mainDir, "sdk/rust"))} }\n\n[profile.release]\nopt-level = "z"\nlto = true\nstrip = true\n`);
    run("cargo", ["build", "--release", "--target", "wasm32-unknown-unknown"], work);
    return { name: base.replace(/\.rs$/, ".wasm"), data: fs.readFileSync(path.join(work, "target/wasm32-unknown-unknown/release/beta_plugin.wasm")) };
  }
  if (base.endsWith(".zig")) {
    fs.copyFileSync(path.join(mainDir, "sdk/zig/ayu.zig"), path.join(work, "ayu.zig"));
    fs.writeFileSync(path.join(work, "plugin.zig"), source);
    run("zig", ["build-exe", "plugin.zig", "-target", "wasm32-freestanding", "-fno-entry", "-rdynamic", "-O", "ReleaseSmall"], work);
    return { name: base.replace(/\.zig$/, ".wasm"), data: addManifest(fs.readFileSync(path.join(work, "plugin.wasm")), manifestFor(file, source)) };
  }
  if (base.endsWith(".go")) {
    fs.writeFileSync(path.join(work, "main.go"), source);
    fs.writeFileSync(path.join(work, "go.mod"), `module betaplugin\n\ngo 1.22\n\nrequire github.com/murk-sus/ayugram-sdk v0.0.0\n\nreplace github.com/murk-sus/ayugram-sdk => ${path.join(mainDir, "sdk/tinygo")}\n`);
    run("tinygo", ["build", "-o", "plugin.wasm", "-target", "wasm-unknown", "-opt", "z", "-no-debug", "./"], work);
    return { name: base.replace(/\.go$/, ".wasm"), data: addManifest(fs.readFileSync(path.join(work, "plugin.wasm")), manifestFor(file, source)) };
  }
  throw new Error("Unsupported file type: " + base);
}

let failed = 0;
for (const file of files) {
  const [, id] = file.split("/");
  const outDir = path.join("beta-out", id);
  const status = { file: path.basename(file), at: new Date().toISOString(), actor };
  try {
    if (!allowedIds.has(id)) throw new Error(`Telegram ID ${id} is not in developers/ID: build this plugin on your computer with the SDK.`);
    const mapped = loginOf(id);
    if (mapped && mapped !== actor) throw new Error(`The folder ${id} belongs to GitHub user ${mapped}, not ${actor}.`);
    if (logins[actor] !== undefined && String(logins[actor]) !== id) throw new Error(`GitHub user ${actor} builds into ${logins[actor]}, not ${id}.`);
    const result = build(file);
    if (result.data.length > 2 * 1024 * 1024) throw new Error("The built plugin is larger than 2 MB.");
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(path.join(outDir, result.name), result.data);
    Object.assign(status, { ok: true, output: result.name, sha256: sha256(result.data), size: result.data.length });
    console.log(`built ${file} -> ${outDir}/${result.name}`);
  } catch (error) {
    failed += 1;
    const message = String(error.stderr ?? error.message ?? error).slice(0, 4000);
    Object.assign(status, { ok: false, error: message });
    console.error(`failed ${file}: ${message}`);
  }
  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, path.basename(file) + ".status.json"), JSON.stringify(status, null, 2) + "\n");
}
// Status files report failures to the app; the job itself only fails on infrastructure errors.
console.log(`${files.length - failed}/${files.length} built`);
