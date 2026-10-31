// ==AyuPlugin==
// @id minimal-ui
// @name Minimal UI
// @author murk-sus & dsn2fvhmn4-lgtm
// @version 1.0
// @description A calmer Telegram: hides stories, similar channels, Premium statuses, the greeting sticker and the fast-share button while enabled. Turning the plugin off brings everything back.
// @tags interface
// ==/AyuPlugin==

for (const feature of ['stories', 'similarChannels', 'premiumStatuses', 'greetingSticker', 'fastShare']) {
    ayu.features.disable(feature);
}
ayu.log('minimal UI on');
