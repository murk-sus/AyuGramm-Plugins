#!/usr/bin/env node
// Catalog checks for every pull request: plugin headers, permissions, @connect hosts, size limits,
// and that index.json points at files whose SHA-256 and size match.
//   node tools/validate.mjs
import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const permissions = new Set(["ui", "menu", "profile", "overlay", "fonts", "badges", "clipboard", "device", "haptics", "network", "messages", "messages.read", "ai", "secrets", "composer", "notifications", "links", "screens", "commands"]);
const problems = [];
const problem = (file, text) => problems.push(`${path.relative(root, file)}: ${text}`);

function header(source, prefix) {
  const fields = {};
  for (const line of source.split("\n").slice(0, 80)) {
    const trimmed = line.trim();
    if (!trimmed.startsWith(prefix)) continue;
    const body = trimmed.slice(prefix.length).trim();
    if (!body.startsWith("@")) continue;
    const space = body.indexOf(" ");
    const key = (space < 0 ? body.slice(1) : body.slice(1, space)).toLowerCase();
    fields[key] = space < 0 ? "" : body.slice(space + 1).trim();
  }
  for (const match of source.matchAll(/^__(\w+)__\s*=\s*["'](.+?)["']\s*$/gm)) {
    fields[match[1].toLowerCase()] ??= match[2];
  }
  return fields;
}

function wasmManifest(data) {
  let offset = 8;
  const leb = () => {
    let value = 0, shift = 0, byte;
    do { byte = data[offset++]; value |= (byte & 0x7f) << shift; shift += 7; } while (byte & 0x80);
    return value;
  };
  while (offset < data.length) {
    const id = data[offset++];
    const size = leb();
    const end = offset + size;
    if (id === 0) {
      const nameLength = leb();
      const name = data.subarray(offset, offset + nameLength).toString();
      if (name === "ayu.manifest") return JSON.parse(data.subarray(offset + nameLength, end).toString());
    }
    offset = end;
  }
  return null;
}

function checkFields(file, fields) {
  if (!/^[a-z0-9_-]{1,64}$/.test(fields.id ?? "")) problem(file, "@id must be 1–64 of a-z, 0-9, - and _");
  if (!fields.name) problem(file, "missing @name");
  if (!fields.version) problem(file, "missing @version");
  const declared = String(fields.permissions ?? "").split(/[\s,]+/).filter(Boolean).map((p) => p.toLowerCase());
  for (const permission of declared) if (!permissions.has(permission)) problem(file, `unknown permission ${permission}`);
  const hosts = String(fields.connect ?? "").split(/[\s,]+/).filter(Boolean);
  for (const host of hosts) if (host.includes("/") || (host.includes("*") && !host.startsWith("*."))) problem(file, `bad @connect host ${host}`);
  if (hosts.length && !declared.includes("network")) problem(file, "@connect needs the network permission");
}

function walk(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => entry.isDirectory() ? walk(path.join(directory, entry.name)) : [path.join(directory, entry.name)]);
}

for (const file of walk(path.join(root, "plugins"))) {
  const data = fs.readFileSync(file);
  if (file.endsWith(".js")) {
    if (data.length > 512 * 1024) problem(file, "larger than 512 KB");
    checkFields(file, header(data.toString(), "//"));
  } else if (file.endsWith(".py")) {
    if (data.length > 512 * 1024) problem(file, "larger than 512 KB");
    checkFields(file, header(data.toString(), "#"));
  } else if (file.endsWith(".wasm")) {
    if (data.length > 2 * 1024 * 1024) problem(file, "larger than 2 MB");
    const manifest = wasmManifest(data);
    if (!manifest) problem(file, "no ayu.manifest section");
    else checkFields(file, { ...manifest, permissions: (manifest.permissions ?? []).join(","), connect: (manifest.connect ?? []).join(",") });
  }
}

const index = JSON.parse(fs.readFileSync(path.join(root, "index.json"), "utf8"));
const prefix = "https://raw.githubusercontent.com/murk-sus/AyuGramm-Plugins/main/";
for (const plugin of index.plugins) {
  if (!plugin.url?.startsWith(prefix)) { problems.push(`index.json: ${plugin.id} has a url outside this repository`); continue; }
  const file = path.join(root, plugin.url.slice(prefix.length));
  if (!fs.existsSync(file)) { problems.push(`index.json: ${plugin.id} points at a missing file`); continue; }
  const data = fs.readFileSync(file);
  const sha = createHash("sha256").update(data).digest("hex");
  if (sha !== plugin.sha256) problems.push(`index.json: ${plugin.id} sha256 does not match the file`);
  if (data.length !== plugin.size) problems.push(`index.json: ${plugin.id} size does not match the file`);
}

if (problems.length) {
  console.error(problems.map((line) => "✗ " + line).join("\n"));
  process.exit(1);
}
console.log(`✓ ${index.plugins.length} catalog entries and their files are valid`);
