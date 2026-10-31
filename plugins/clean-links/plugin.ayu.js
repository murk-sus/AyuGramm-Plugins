// ==AyuPlugin==
// @id clean-links
// @name Clean links
// @author murk-sus & dsn2fvhmn4-lgtm
// @version 1.0
// @description Removes tracking parameters (utm_*, fbclid, gclid, si, igsh…) from links you send, so they do not reveal where you found them.
// @tags privacy, links
// ==/AyuPlugin==

const tracking = /^(utm_[a-z]+|fbclid|gclid|dclid|yclid|mc_cid|mc_eid|igsh|igshid|si|feature|ref_src|ref_url|spm|_hsenc|_hsmi|mkt_tok|vero_id|oly_anon_id|oly_enc_id|wickedid|trk|trkCampaign)$/i;

function clean(url) {
    const hash = url.indexOf('#');
    const fragment = hash >= 0 ? url.slice(hash) : '';
    const base = hash >= 0 ? url.slice(0, hash) : url;
    const query = base.indexOf('?');
    if (query < 0) return url;
    const kept = base.slice(query + 1).split('&').filter((pair) => pair && !tracking.test(pair.split('=')[0]));
    return base.slice(0, query) + (kept.length ? '?' + kept.join('&') : '') + fragment;
}

ayu.hooks.after(ayu.hooks.points.outgoingText, (text) => {
    if (!/https?:\/\//i.test(text)) return undefined;
    return text.replace(/https?:\/\/[^\s<>"]+/gi, (url) => clean(url));
});
