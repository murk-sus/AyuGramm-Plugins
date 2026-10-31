// ==AyuPlugin==
// @id my-plugin
// @name My plugin
// @author your-github-name
// @version 1.0
// @description One or two sentences about what the plugin does.
// @tags text
// ==/AyuPlugin==

// Runs before the built-in outgoing-text handler. Return a string to change the text,
// anything else to leave it as it is. `ctx` is { peerId, isSecret }.
ayu.hooks.before(ayu.hooks.points.outgoingText, (text, ctx) => {
    return undefined;
});

// Other building blocks:
//   ayu.hooks.after(point, fn)      — after the built-in handler
//   ayu.hooks.replace(point, fn)    — instead of it (one plugin per point)
//   ayu.features.disable('stories') — switch a feature off while the plugin runs
//   ayu.on('chatOpen', ({ peerId }) => {})
//   ayu.storage.get(key) / ayu.storage.set(key, value)
//   ayu.toast('text'), console.log(...)
