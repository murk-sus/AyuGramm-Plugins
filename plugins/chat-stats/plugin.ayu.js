// ==AyuPlugin==
// @id chat-stats
// @name Статистика чата
// @author @selfharmenthusiast
// @version 1.0.0
// @description Статистика до 100 последних доступных сообщений: входящие, исходящие, авторы и объём текста. AyuGramm SDK 27.5.
// @permissions messages.read, screens, ui, menu, clipboard, commands
// ==/AyuPlugin==

(function () {
    'use strict';
    var stopped = false;
    var generation = 0;
    var sequence = 0;
    var busy = false;
    var reports = Object.create(null);
    var order = [];
    var buttonId = 'chat-stats-open';

    ayu.settings.declare([
        { key: 'limit', type: 'select', title: 'Размер выборки', default: '100', options: [
            { value: '20', title: 'До 20 сообщений' },
            { value: '50', title: 'До 50 сообщений' },
            { value: '100', title: 'До 100 сообщений' }
        ] },
        { key: 'authors', type: 'slider', title: 'Авторов в списке', min: 3, max: 15, step: 1, default: 8 },
        { key: 'details', type: 'toggle', title: 'Подробная статистика текста', default: true },
        { key: 'info', type: 'preview', title: 'О выборке', default:
            'Анализируются сообщения из кеша на этом устройстве. Это не вся история чата. Фото без подписи учитывается как сообщение без текста.' }
    ]);

    function setting(key, fallback) {
        var v = ayu.settings.get(key);
        return v == null ? fallback : String(v);
    }
    function limit() {
        var n = Number(setting('limit', '100'));
        return [20, 50, 100].indexOf(n) >= 0 ? n : 100;
    }
    function fmt(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' '); }
    function pad(n) { return n < 10 ? '0' + n : String(n); }
    function date(timestamp) {
        if (!Number.isFinite(timestamp)) return 'Нет данных';
        var d = new Date(timestamp * 1000);
        return pad(d.getDate()) + '.' + pad(d.getMonth() + 1) + '.' + d.getFullYear() + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
    }
    function value(id, title, v) { return { id: id, type: 'value', title: title, value: String(v) }; }
    function percent(n, total) { return total ? Math.round(n * 100 / total) : 0; }

    function analyze(raw, peerId) {
        var seen = Object.create(null);
        var messages = raw.filter(function (m) {
            if (!m || m.id == null || (m.peerId != null && String(m.peerId) !== peerId)) return false;
            var key = String(m.id);
            if (seen[key]) return false;
            seen[key] = true;
            return true;
        }).slice(0, 100);
        var stats = { peerId: peerId, total: messages.length, incoming: 0, outgoing: 0,
            unknownDirection: 0, withText: 0, chars: 0, words: 0, longest: 0,
            first: Infinity, last: -Infinity, authors: [], missingAuthor: 0 };
        var byAuthor = Object.create(null);
        messages.forEach(function (m) {
            if (m.outgoing === true) stats.outgoing++;
            else if (m.outgoing === false) stats.incoming++;
            else stats.unknownDirection++;
            var text = typeof m.text === 'string' ? m.text : '';
            if (text.trim()) stats.withText++;
            var length = Array.from(text).length;
            stats.chars += length;
            stats.words += (text.match(/\S+/g) || []).length;
            stats.longest = Math.max(stats.longest, length);
            var timestamp = Number(m.date);
            if (m.date != null && Number.isFinite(timestamp) && timestamp > 0 && timestamp < 8640000000000) {
                stats.first = Math.min(stats.first, timestamp);
                stats.last = Math.max(stats.last, timestamp);
            }
            if (m.authorId == null || String(m.authorId) === '') { stats.missingAuthor++; return; }
            var id = String(m.authorId);
            if (!byAuthor[id]) byAuthor[id] = { id: id, count: 0, outgoing: false };
            byAuthor[id].count++;
            byAuthor[id].outgoing = byAuthor[id].outgoing || m.outgoing === true;
        });
        stats.authors = Object.keys(byAuthor).map(function (id) { return byAuthor[id]; }).sort(function (a, b) {
            return b.count - a.count || a.id.localeCompare(b.id);
        });
        return stats;
    }

    function titleForAuthor(author) {
        return author.outgoing ? 'Вы · ID ' + author.id : 'ID ' + author.id;
    }
    function summary(s) {
        return 'Статистика выборки чата ' + s.peerId + '\n' +
            'Доступно сообщений: ' + s.total + '\n' +
            'Входящие: ' + s.incoming + '\n' + 'Исходящие: ' + s.outgoing + '\n' +
            'С текстом: ' + s.withText + '\n' + 'Без текста: ' + (s.total - s.withText) + '\n' +
            'Символов: ' + s.chars + '\n' + 'Слов (по пробелам): ' + s.words + '\n' +
            'Период: ' + date(s.first) + ' — ' + date(s.last) + '\n' +
            'Это последние доступные сообщения из локального кеша, не вся история.';
    }
    function show(s, requested) {
        var screenId = 'chat-stats-' + (++sequence);
        reports[screenId] = s;
        order.push(screenId);
        if (order.length > 10) delete reports[order.shift()];
        var main = [value('total', '📨 В выборке', fmt(s.total)),
            value('incoming', '📥 Входящие', fmt(s.incoming) + ' · ' + percent(s.incoming, s.total) + '%'),
            value('outgoing', '📤 Исходящие', fmt(s.outgoing) + ' · ' + percent(s.outgoing, s.total) + '%'),
            value('with-text', 'С текстом', fmt(s.withText)),
            value('without-text', 'Без текста', fmt(s.total - s.withText))];
        if (s.unknownDirection) main.push(value('unknown-direction', 'Направление не указано', s.unknownDirection));
        var sections = [{ title: 'Обзор · до ' + requested + ' сообщений', rows: main,
            footer: 'Чат: ' + s.peerId + '. Только сообщения, доступные на этом устройстве; число всей переписки SDK не передаёт.' }];
        if (s.total) {
            sections.push({ title: '🗓 Период выборки', rows: [
                value('first', 'Самое раннее', date(s.first)), value('last', 'Самое позднее', date(s.last))
            ], footer: 'Время в часовом поясе iPhone.' });
        }
        if (s.total && setting('details', '1') === '1') {
            sections.push({ title: '✍️ Текст', rows: [
                value('chars', 'Символов', fmt(s.chars)), value('words', 'Слов', fmt(s.words)),
                value('average', 'Символов на сообщение', Math.round(s.chars / s.total)),
                value('longest', 'Самое длинное · символов', fmt(s.longest))
            ], footer: 'Слова разделяются пробелами. Учитываются тексты и подписи, переданные клиентом.' });
        }
        if (s.authors.length || s.missingAuthor) {
            var top = Math.max(3, Math.min(15, Number(setting('authors', '8')) || 8));
            var authorRows = s.authors.slice(0, top).map(function (a, i) {
                return value('author-' + i, titleForAuthor(a), a.count + ' · ' + percent(a.count, s.total) + '%');
            });
            if (s.missingAuthor) authorRows.push(value('missing-author', 'Без ID автора', s.missingAuthor));
            sections.push({ title: '👥 Авторы', rows: authorRows,
                footer: 'Разных ID в выборке: ' + s.authors.length + '. SDK не передаёт имена авторов.' });
        }
        if (!s.total) sections.push({ rows: [{ id: 'empty', type: 'text', title: 'Пока нет доступных сообщений',
            subtitle: 'Открой переписку, дождись загрузки сообщений и снова нажми «Статистика».' }] });
        sections.push({ rows: [{ id: 'copy', type: 'button', title: 'Скопировать сводку' }],
            footer: 'Для нового снимка закрой эту страницу и снова нажми «Статистика» в чате.' });
        ayu.screens.show({ id: screenId, title: 'Статистика чата', sections: sections });
    }

    function open(peerId) {
        if (stopped) return;
        if (peerId == null || String(peerId) === '') { ayu.toast('Открой чат и нажми «Статистика».'); return; }
        if (busy) { ayu.toast('Статистика уже загружается…'); return; }
        if (!ayu.messages || typeof ayu.messages.get !== 'function' || !ayu.screens || typeof ayu.screens.show !== 'function') {
            ayu.toast('Нужна IPA AyuGramm с SDK 27.5: messages.get и screens.show.'); return;
        }
        busy = true;
        var token = ++generation;
        var requested = limit();
        var id = String(peerId);
        var timeout = setTimeout(function () {
            if (generation !== token || stopped) return;
            generation++; busy = false;
            ayu.toast('Нет ответа от SDK. Проверь разрешение «Чтение сообщений» и версию IPA.');
        }, 10000);
        ayu.messages.get({ peerId: id, limit: requested }).then(function (messages) {
            clearTimeout(timeout);
            if (generation !== token || stopped) return;
            busy = false;
            if (!Array.isArray(messages)) throw new Error('Клиент вернул неверный ответ.');
            show(analyze(messages, id), requested);
        }).catch(function (error) {
            clearTimeout(timeout);
            if (generation !== token || stopped) return;
            busy = false;
            ayu.error(String(error));
            ayu.toast('Не удалось прочитать сообщения. Проверь разрешение messages.read и версию IPA.');
        });
    }

    if (ayu.chat && ayu.chat.toolbar && typeof ayu.chat.toolbar.add === 'function') {
        ayu.chat.toolbar.add({ id: buttonId, title: 'Статистика', icon: 'chart.bar.xaxis' }, open);
    }
    if (ayu.ui && ayu.ui.menu) {
        ayu.ui.menu.add({ id: buttonId, title: 'Статистика чата', icon: 'chart.bar.xaxis' });
        ayu.on('menuAction', function (e) { if (e && e.itemId === buttonId) open(e.peerId); });
    }
    if (ayu.commands && typeof ayu.commands.register === 'function') {
        ayu.commands.register('stats', 'Статистика последних сообщений', function (args, ctx) {
            open(ctx && ctx.peerId); return null;
        });
    }
    ayu.on('screenAction', function (e) {
        if (!e || e.rowId !== 'copy' || !reports[e.screenId]) return;
        ayu.clipboard.write(summary(reports[e.screenId]));
        ayu.toast('Сводка скопирована.');
    });
    ayu.on('accountChange', function () {
        generation++; busy = false; reports = Object.create(null); order = [];
    });
    ayu.on('unload', function () {
        stopped = true; generation++; reports = Object.create(null); order = [];
        if (ayu.chat && ayu.chat.toolbar) ayu.chat.toolbar.remove(buttonId);
        if (ayu.ui && ayu.ui.menu) ayu.ui.menu.remove(buttonId);
    });
})();
