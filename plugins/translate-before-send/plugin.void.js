// ==VoidPlugin==
// @id translate-before-send
// @name Translate before sending
// @name:ru Перевод перед отправкой
// @author murk-sus
// @version 1.0
// @description A 🌐 button above the composer translates the draft before you send it. The translation runs through Google's public endpoint; the text leaves the device only when you tap the button.
// @description:ru Кнопка 🌐 над полем ввода переводит набранный текст перед отправкой. Перевод идёт через публичный endpoint Google; текст покидает устройство только по нажатию.
// @permissions composer, ui, network
// @connect translate.googleapis.com
// @tags text, translation
// ==/VoidPlugin==

(function () {
    var languages = [
        { value: 'en', title: 'English' },
        { value: 'ru', title: 'Русский' },
        { value: 'uk', title: 'Українська' },
        { value: 'de', title: 'Deutsch' },
        { value: 'es', title: 'Español' },
        { value: 'fr', title: 'Français' },
        { value: 'it', title: 'Italiano' },
        { value: 'pt', title: 'Português' },
        { value: 'tr', title: 'Türkçe' },
        { value: 'pl', title: 'Polski' },
        { value: 'zh', title: '中文' },
        { value: 'ja', title: '日本語' },
        { value: 'ko', title: '한국어' },
        { value: 'ar', title: 'العربية' },
        { value: 'kk', title: 'Қазақша' }
    ];

    voidgram.settings.declare([
        {
            key: 'target',
            type: 'select',
            title: 'Переводить на',
            subtitle: 'Кнопка над клавиатурой переводит черновик на этот язык',
            default: 'en',
            options: languages
        }
    ]);

    function targetLanguage() {
        return String(voidgram.settings.get('target') || 'en');
    }

    function translate(text, to) {
        var url = 'https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=' + encodeURIComponent(to) + '&dt=t&q=' + encodeURIComponent(text);
        return voidgram.net.fetch(url).then(function (response) {
            if (!response || response.status !== 200) throw new Error('HTTP ' + (response ? response.status : '?'));
            var data = response.json();
            if (!Array.isArray(data) || !Array.isArray(data[0])) throw new Error('Unexpected answer');
            return data[0].map(function (part) { return part && part[0] ? String(part[0]) : ''; }).join('');
        });
    }

    voidgram.composer.addButton({ id: 'translate', title: 'Перевод', icon: 'globe' });

    voidgram.on('composerButton', function (payload) {
        if (!payload || payload.id !== 'translate') return;
        var text = String(payload.text || '').trim();
        if (!text) {
            voidgram.toast('Сначала наберите текст');
            return;
        }
        var to = targetLanguage();
        voidgram.toast('Перевод на ' + to + '…');
        translate(text, to).then(function (result) {
            if (result && result.trim()) {
                voidgram.composer.setText(result);
            } else {
                voidgram.toast('Не удалось перевести');
            }
        }).catch(function (error) {
            voidgram.error('translate-before-send: ' + (error && error.message ? error.message : error));
            voidgram.toast('Перевод недоступен');
        });
    });
})();
