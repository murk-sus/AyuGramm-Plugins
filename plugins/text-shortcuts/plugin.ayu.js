// ==AyuPlugin==
// @id text-shortcuts
// @name Text shortcuts
// @author murk-sus & dsn2fvhmn4-lgtm
// @version 1.0
// @description Expands shortcuts in outgoing messages: :shrug: → ¯\_(ツ)_/¯, :lenny: → ( ͡° ͜ʖ ͡°), :tableflip: → (╯°□°)╯︵ ┻━┻, ->, <-, (c), (tm) and more.
// @tags text, fun
// ==/AyuPlugin==

const shortcuts = {
    ':shrug:': '¯\\_(ツ)_/¯',
    ':lenny:': '( ͡° ͜ʖ ͡°)',
    ':tableflip:': '(╯°□°)╯︵ ┻━┻',
    ':unflip:': '┬─┬ノ( º _ ºノ)',
    ':disapproval:': 'ಠ_ಠ',
    ':sparkles:': '✨',
    ':check:': '✅',
    ':cross:': '❌',
    '->': '→',
    '<-': '←',
    '=>': '⇒',
    '(c)': '©',
    '(r)': '®',
    '(tm)': '™',
    '+-': '±',
    '...': '…'
};

const keys = Object.keys(shortcuts).sort((a, b) => b.length - a.length);
const escape = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const pattern = new RegExp(keys.map(escape).join('|'), 'g');

ayu.hooks.after(ayu.hooks.points.outgoingText, (text) => {
    // Leave code alone.
    if (text.includes('`')) return undefined;
    return text.replace(pattern, (match) => shortcuts[match]);
});
