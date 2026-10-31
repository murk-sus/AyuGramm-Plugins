// ==AyuPlugin==
// @id smart-quotes
// @name Smart quotes
// @author murk-sus & dsn2fvhmn4-lgtm
// @version 1.1
// @description Straight quotes become «ёлочки» in Russian text and “curly” quotes otherwise; "--" becomes an em dash.
// @tags text, typography
// ==/AyuPlugin==

function curly(text) {
    const russian = /[а-яё]/i.test(text);
    let open = true;
    return text
        .replace(/(^|[^-])--(?!-)/g, '$1—')
        .replace(/"/g, () => {
            const mark = russian ? (open ? '«' : '»') : (open ? '“' : '”');
            open = !open;
            return mark;
        });
}

ayu.hooks.after(ayu.hooks.points.outgoingText, curly);
