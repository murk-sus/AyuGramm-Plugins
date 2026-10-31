# AyuGramm Plugins

Каталог код-плагинов для [AyuGramm-IOS](https://github.com/dsn2fvhmn4-lgtm/AyuGramm-IOS).
AyuGram загружает [`index.json`](index.json) из этого репозитория и показывает плагины
во вкладке **Настройки → AyuGram → Плагины → Каталог**.

## Плагины

| Плагин | Что делает |
|---|---|
| [Smart quotes](plugins/smart-quotes/plugin.ayu.js) | `"кавычки"` → «ёлочки» / “curly”, `--` → тире |
| [Layout fix](plugins/layout-fix/plugin.ayu.js) | Исправляет раскладку: `ghbdtn` → `привет`, `руддщ` → `hello` |
| [Clean links](plugins/clean-links/plugin.ayu.js) | Убирает из ссылок `utm_*`, `fbclid`, `si` и другие метки слежки |
| [Text shortcuts](plugins/text-shortcuts/plugin.ayu.js) | `:shrug:` → `¯\_(ツ)_/¯`, `->` → `→`, `(c)` → `©` и др. |
| [Minimal UI](plugins/minimal-ui/plugin.ayu.js) | Скрывает истории, похожие каналы, Premium-статусы и др. |

## Установка

В приложении: **Плагины → Каталог** → выберите плагин → **Установить**. Перед установкой
показываются автор, описание и предупреждение; файл проверяется по SHA-256 из индекса.

Вручную: скачайте `plugin.ayu.js` и откройте его через **Плагины → «+»**.

## Как устроен плагин

Каждый плагин — один файл `plugins/<id>/plugin.ayu.js` с заголовком:

```js
// ==AyuPlugin==
// @id my-plugin
// @name My plugin
// @author your-github-name
// @version 1.0
// @description What it does.
// @tags text, privacy
// ==/AyuPlugin==

ayu.hooks.before(ayu.hooks.points.outgoingText, (text, ctx) => text.trim());
```

Полный API — в [документации AyuGramm-IOS](https://github.com/dsn2fvhmn4-lgtm/AyuGramm-IOS/blob/main/docs/CODE_PLUGINS.md):
перехват и замена исходящего текста, отключение функций, события, хранилище, тосты, таймеры.

## Прислать свой плагин

1. Скопируйте [`template/plugin.ayu.js`](template/plugin.ayu.js) в `plugins/<ваш-id>/plugin.ayu.js`.
2. `@id` должен совпадать с именем папки (`a-z`, `0-9`, `-`, `_`).
3. Проверьте локально:
   ```sh
   node tools/test_plugins.js
   python3 tools/build_index.py
   ```
4. Откройте pull request. После мержа GitHub Action пересоберёт `index.json`.

Правила: только локальная работа, без сбора данных; плагин должен делать то, что написано в описании.

## Безопасность

Плагины выполняются как код, но в отдельной виртуальной машине JavaScriptCore. У них **нет
доступа к сети, аккаунту, файлам и отправке сообщений**: только текст, переданный в их хуки,
и собственное хранилище. Плагин, который не ответил вовремя, отключается автоматически.
Устанавливайте только то, чему доверяете, и читайте код — он короткий.
