// Loads every catalog plugin against a stand-in of the AyuGram `ayu` API and checks it
// registers cleanly; plugins with known behaviour get concrete assertions.
//   node tools/test_plugins.js
'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

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
    const sandbox = { ayu, console: { log: ayu.log } };
    vm.createContext(sandbox);
    vm.runInContext(fs.readFileSync(file, 'utf8'), sandbox, { filename: file });
    const run = (text) => calls.hooks.reduce((value, hook) => {
        const result = hook.fn(value, { peerId: '1', isSecret: false });
        return typeof result === 'string' ? result : value;
    }, text);
    return { calls, run };
}

const root = path.join(__dirname, '..', 'plugins');
const results = {};
for (const id of fs.readdirSync(root)) {
    const file = path.join(root, id, 'plugin.ayu.js');
    if (fs.existsSync(file)) results[id] = load(file);
}
const known = new Set(['stories', 'similarChannels', 'premiumStatuses', 'greetingSticker', 'fastShare', 'messageShot', 'reactionPicker', 'readSummary', 'editedInfo', 'messageDetails', 'unreadCounters', 'openLinkWarning', 'doubleTapToEdit', 'formattingToolbar', 'keyboardHideOnScroll']);
for (const [id, { calls }] of Object.entries(results)) {
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
