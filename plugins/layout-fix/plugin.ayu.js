// ==AyuPlugin==
// @id layout-fix
// @name Layout fix
// @author murk-sus
// @version 1.0
// @description Fixes text typed in the wrong keyboard layout: "ghbdtn" → "привет", "руддщ" → "hello". Only whole messages that clearly look mistyped are changed.
// @tags text, keyboard
// ==/AyuPlugin==

const en = "`qwertyuiop[]asdfghjkl;'zxcvbnm,./~QWERTYUIOP{}ASDFGHJKL:\"ZXCVBNM<>?";
const ru = "ёйцукенгшщзхъфывапролджэячсмитьбю.ЁЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ,";
const enToRu = {}, ruToEn = {};
for (let i = 0; i < en.length; i++) { enToRu[en[i]] = ru[i]; ruToEn[ru[i]] = en[i]; }

const vowelsRu = /[аеёиоуыэюя]/gi;
const vowelsEn = /[aeiouy]/gi;

function convert(text, table) {
    return Array.from(text).map((ch) => table[ch] || ch).join('');
}

// Latin text with almost no vowels and no links reads as Russian typed on an English layout.
function looksMistypedEnglish(text) {
    const letters = (text.match(/[a-z]/gi) || []).length;
    if (letters < 4 || /https?:|www\.|@/.test(text) || /[а-яё]/i.test(text)) return false;
    const vowels = (text.match(vowelsEn) || []).length;
    const converted = convert(text, enToRu);
    const ruVowels = (converted.match(vowelsRu) || []).length;
    return vowels / letters < 0.2 && ruVowels / letters >= 0.25;
}

function looksMistypedRussian(text) {
    const letters = (text.match(/[а-яё]/gi) || []).length;
    if (letters < 4 || /[a-z]/i.test(text)) return false;
    const vowels = (text.match(vowelsRu) || []).length;
    const converted = convert(text, ruToEn);
    const enVowels = (converted.match(vowelsEn) || []).length;
    return vowels / letters < 0.2 && enVowels / letters >= 0.25;
}

ayu.hooks.before(ayu.hooks.points.outgoingText, (text) => {
    if (looksMistypedEnglish(text)) return convert(text, enToRu);
    if (looksMistypedRussian(text)) return convert(text, ruToEn);
    return undefined;
});
