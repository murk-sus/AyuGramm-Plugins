// ==AyuPlugin==
// @id visual-overlay
// @name Visual Overlay
// @author @gurodesc
// @version 1.2
// @description Частицы (дождь, звёзды, конфетти) поверх приложения, палитра цветов и подпись.
// @permissions overlay
// ==/AyuPlugin==

const OVERLAY_ID = 'visual-overlay';
const LABEL_ID = 'visual-label';

// Палитра: цвет выбирается из списка, коды вводить не нужно.
const PALETTE = [
  { value: '#FFFFFF', title: '⚪ Белый' },
  { value: '#FFD54A', title: '🟡 Золотой' },
  { value: '#FF9F43', title: '🟠 Оранжевый' },
  { value: '#FF4D4F', title: '🔴 Красный' },
  { value: '#3DDC97', title: '🟢 Мятный' },
  { value: '#4DA8FF', title: '🔵 Небесный' },
  { value: '#B388FF', title: '🟣 Лавандовый' },
  { value: '#8E8E93', title: '⚫ Графит' },
];

ayu.settings.declare([
  {
    key: 'effect',
    type: 'select',
    title: 'Эффект',
    subtitle: 'Частицы поверх всего приложения',
    default: 'stars',
    options: [
      { value: 'rain', title: 'Дождь' },
      { value: 'stars', title: 'Звёзды' },
      { value: 'confetti', title: 'Конфетти' },
    ],
  },
  {
    key: 'color',
    type: 'select',
    title: 'Цвет',
    subtitle: 'Выбери из палитры, гуглить коды не нужно',
    default: '#FFFFFF',
    options: PALETTE,
  },
  { key: 'amount', type: 'slider', title: 'Количество', min: 0.1, max: 3, step: 0.1, default: 0.6 },
  { key: 'speed', type: 'slider', title: 'Скорость', min: 0.1, max: 3, step: 0.1, default: 0.8 },
  {
    key: 'label',
    type: 'text',
    title: 'Подпись',
    subtitle: 'Текст поверх приложения, пусто — без подписи',
    default: '',
  },
  {
    key: 'corner',
    type: 'select',
    title: 'Место подписи',
    default: 'bottomRight',
    options: [
      { value: 'topLeft', title: 'Сверху слева' },
      { value: 'topRight', title: 'Сверху справа' },
      { value: 'bottomLeft', title: 'Снизу слева' },
      { value: 'bottomRight', title: 'Снизу справа' },
      { value: 'center', title: 'По центру' },
    ],
  },
]);

function num(key, fallback) {
  const v = parseFloat(ayu.settings.get(key));
  return Number.isFinite(v) ? v : fallback;
}

// Берёт цвет из палитры; старые значения вне списка заменяются белым.
function colorValue() {
  const v = (ayu.settings.get('color') || '').toUpperCase();
  return PALETTE.some((p) => p.value === v) ? v : '#FFFFFF';
}

function clearAll() {
  ayu.ui.overlay.remove(OVERLAY_ID);
  ayu.ui.overlay.remove(LABEL_ID);
}

// Пересоздаёт эффект по текущим настройкам.
function apply() {
  clearAll();
  const color = colorValue();
  ayu.ui.overlay.create({
    id: OVERLAY_ID,
    effect: ayu.settings.get('effect') || 'stars',
    amount: num('amount', 0.6),
    speed: num('speed', 0.8),
    color: color,
  });
  const label = (ayu.settings.get('label') || '').trim();
  if (label) {
    ayu.ui.overlay.addText({
      id: LABEL_ID,
      text: label,
      anchor: ayu.settings.get('corner') || 'bottomRight',
      size: 20,
      color: color,
    });
  }
}

ayu.on('load', apply);
ayu.on('settingsChange', apply);
ayu.on('unload', clearAll);
