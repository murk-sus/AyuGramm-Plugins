// Loads every catalog plugin against a stand-in of the VoidGram `ayu` API and checks it
// registers cleanly; plugins with known behaviour get concrete assertions.
//   node tools/test_plugins.js               every plugin in plugins/
//   node tools/test_plugins.js FILE...       only these files (the team bot checks uploads this way)
// The stand-in implements what the assertions need (hooks, features, storage). Every other part
// of the API (settings, ui, net, ai, messages…) is a no-op that accepts any call, so a plugin
// that uses the full API still loads; it only fails on its own errors.
'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

/// Any property is another stub and any call returns one: ayu.ui.overlay.addClock(...) works.
function stub() {
    const target = function () {};
    return new Proxy(target, {
        get(_, key) {
            if (key === Symbol.toPrimitive) return () => '';
            if (key === 'then') return undefined; // not a promise
            if (key === Symbol.iterator) return function* () {};
            return stub();
        },
        apply() { return stub(); },
        construct() { return stub(); }
    });
}

/// The object itself where it has the key, a stub where it does not, at every level.
function lenient(object) {
    return new Proxy(object, {
        get(target, key) {
            if (key in target) {
                const value = target[key];
                return value && typeof value === 'object' ? lenient(value) : value;
            }
            return typeof key === 'symbol' ? undefined : stub();
        }
    });
}

function load(file) {
    const calls = { hooks: [], features: [], logs: [] };
    const register = (point, mode, fn) => {
        if (typeof fn !== 'function') throw new TypeError('Hook handler must be a function');
        calls.hooks.push({ point, mode, fn });
    };
    const ayu = {
        log: (...args) => calls.logs.push(args.join(' ')),
        warn: () => {}, error: () => {}, toast: () => {}, on: () => {},
        hooks: {
            before: (p, f) => register(p, 'before', f),
            after: (p, f) => register(p, 'after', f),
            replace: (p, f) => register(p, 'replace', f),
            points: { outgoingText: 'message.outgoing.text' }
        },
        features: { disable: (n) => calls.features.push(n), enable: () => {} },
        storage: { get: () => null, set: () => {} }
    };
    const noop = () => 0;
    const sandbox = { ayu: lenient(ayu), voidgram: lenient(ayu), $void: lenient(ayu), console: { log: ayu.log, warn: noop, error: noop, info: noop },
                      setTimeout: noop, setInterval: noop, clearTimeout: noop, clearInterval: noop };
    vm.createContext(sandbox);
    vm.runInContext(fs.readFileSync(file, 'utf8'), sandbox, { filename: file, timeout: 2000 });
    const run = (text) => calls.hooks.reduce((value, hook) => {
        const result = hook.fn(value, { peerId: '1', isSecret: false });
        return typeof result === 'string' ? result : value;
    }, text);
    return { calls, run };
}

const files = process.argv.slice(2);
if (files.length) {
    for (const file of files) load(file);
    console.log(`plugins: ${files.length} loaded`);
    process.exit(0);
}

const root = path.join(__dirname, '..', 'plugins');
const results = {};
const community = new Set();
for (const id of fs.readdirSync(root)) {
    const candidates = [path.join(root, id, 'plugin.void.js'), path.join(root, id, 'plugin.ayu.js')];
    const file = candidates.find((candidate) => fs.existsSync(candidate));
    if (!file) continue;
    results[id] = load(file);
    // Plugins by other authors (meta.json from the team bot) only have to load; the checks
    // below describe the team's own plugins.
    if (fs.existsSync(path.join(root, id, 'meta.json'))) community.add(id);
}
const known = new Set(['stories', 'similarChannels', 'premiumStatuses', 'greetingSticker', 'fastShare', 'messageShot', 'reactionPicker', 'readSummary', 'editedInfo', 'messageDetails', 'unreadCounters', 'openLinkWarning', 'doubleTapToEdit', 'formattingToolbar', 'keyboardHideOnScroll']);
for (const [id, { calls }] of Object.entries(results)) {
    if (community.has(id)) continue;
    for (const hook of calls.hooks) assert.strictEqual(hook.point, 'message.outgoing.text', `${id}: unknown hook point`);
    for (const feature of calls.features) assert(known.has(feature), `${id}: unknown feature ${feature}`);
}

const q = results['smart-quotes'].run;
assert.strictEqual(q('он сказал "привет" -- да'), 'он сказал «привет» — да');
assert.strictEqual(q('say "hi"'), 'say “hi”');

const l = results['layout-fix'].run;
assert.strictEqual(l('ghbdtn rfr ltkf'), 'привет как дела');
assert.strictEqual(l('руддщ цщкдв'), 'hello world');
assert.strictEqual(l('hello world'), 'hello world');
assert.strictEqual(l('https://x.y/abc'), 'https://x.y/abc');

const c = results['clean-links'].run;
assert.strictEqual(c('see https://ex.com/a?utm_source=x&id=5&fbclid=zz#top ok'), 'see https://ex.com/a?id=5#top ok');
assert.strictEqual(c('https://youtu.be/abc?si=TRACK'), 'https://youtu.be/abc');
assert.strictEqual(c('no links here'), 'no links here');

const s = results['text-shortcuts'].run;
assert.strictEqual(s('ok :shrug: -> (c)'), 'ok ¯\\_(ツ)_/¯ → ©');
assert.strictEqual(s('`a -> b`'), '`a -> b`');

assert.deepStrictEqual(results['minimal-ui'].calls.features, ['stories', 'similarChannels', 'premiumStatuses', 'greetingSticker', 'fastShare']);

console.log(`plugins: ${Object.keys(results).length} loaded, all checks passed`);
