// 図表：コート図・シュートチャート・レーダーチャート・折れ線グラフ・成長記録カレンダー（すべて SVG / DOM で描画）

import { h, s, 日付を読む } from './共通.js';

// ハーフコート 横500×縦470（上がゴール側）。1m ≒ 33.3
export const コート = { 幅: 500, 奥行: 470, ゴール: { x: 250, y: 52.5 } };

export function コートの線(色 = 'var(--コート線)', リング色 = 'var(--リング)') {
  const 線 = { fill: 'none', stroke: 色, 'stroke-width': 2.5 };
  const 右 = { x: 470, y: 99.7 };
  return s('g', { class: 'コート線' },
    s('rect', { x: 1.5, y: 1.5, width: 497, height: 467, ...線 }),
    s('rect', { x: 168.3, y: 0, width: 163.4, height: 193.3, ...線 }),
    s('circle', { cx: 250, cy: 193.3, r: 60, ...線 }),
    s('path', { d: 'M 208.3 52.5 A 41.7 41.7 0 0 0 291.7 52.5', ...線 }),
    s('line', { x1: 220, y1: 40, x2: 280, y2: 40, ...線, 'stroke-width': 4 }),
    s('circle', { cx: 250, cy: 52.5, r: 7.5, ...線, stroke: リング色 }),
    s('path', { d: `M 30 0 L 30 99.7 A 225 225 0 0 0 ${右.x} ${右.y} L 470 0`, ...線 }),
    s('path', { d: 'M 190 470 A 60 60 0 0 1 310 470', ...線 }));
}

export const エリア位置 = {
  ゴール下: [250, 78],
  ペイント: [250, 160],
  ミドル左: [105, 125],
  ミドル正面: [250, 240],
  ミドル右: [395, 125],
  '3P左コーナー': [15, 45],
  '3P左ウイング': [62, 262],
  '3Pトップ': [250, 330],
  '3P右ウイング': [438, 262],
  '3P右コーナー': [485, 45],
};

export function 成功率の色(率) {
  if (率 === null || 率 === undefined) return 'var(--薄)';
  if (率 >= 50) return 'var(--良)';
  if (率 >= 35) return 'var(--注意)';
  return 'var(--悪)';
}

// エリア一覧 [{zone, a, m, pct}]。選択時(エリア名) を渡すとタップで選べる
export function シュートチャート(エリア一覧, { 選択中 = null, 選択時 = null } = {}) {
  const 対応 = Object.fromEntries(エリア一覧.map((z) => [z.zone, z]));
  return s('svg', { viewBox: '-5 -5 510 400', class: 'シュートチャート', role: 'img', 'aria-label': 'シュートチャート' },
    s('rect', { x: -5, y: -5, width: 510, height: 480, fill: 'var(--コート)' }),
    コートの線(),
    Object.entries(エリア位置).map(([名前, [x, y]]) => {
      const z = 対応[名前] || { a: 0, m: 0, pct: null };
      const 率 = z.a ? Math.round((z.m / z.a) * 1000) / 10 : null;
      return s('g', {
        class: `エリア ${選択時 ? '押せる' : ''} ${選択中 === 名前 ? '選択中' : ''}`,
        transform: `translate(${Math.min(Math.max(x, 36), 464)} ${y})`,
        onclick: 選択時 ? () => 選択時(名前) : null,
      },
      s('circle', { r: 33, fill: 成功率の色(率), 'fill-opacity': z.a ? 0.85 : 0.35, stroke: 選択中 === 名前 ? 'var(--強調)' : 'white', 'stroke-width': 選択中 === 名前 ? 5 : 2 }),
      s('text', { y: -6, 'text-anchor': 'middle', class: 'エリア率' }, 率 === null ? '—' : `${Math.round(率)}%`),
      s('text', { y: 14, 'text-anchor': 'middle', class: 'エリア数' }, `${z.m}/${z.a}`));
    }));
}

// 系列 [{名前, 値: [0-100 or null...], 色}]、軸名 [..]
export function レーダーチャート(軸名, 系列) {
  const n = 軸名.length;
  const 中心 = 150;
  const 半径 = 100;
  const 点 = (i, 値) => {
    const 角 = -Math.PI / 2 + (2 * Math.PI * i) / n;
    return [中心 + Math.cos(角) * 半径 * (値 / 100), 中心 + Math.sin(角) * 半径 * (値 / 100)];
  };
  if (n < 3) return h('p', { class: '空' }, 'レーダーチャートにはスキルが3つ以上必要です');
  return h('figure', { class: 'レーダー' },
    s('svg', { viewBox: '0 0 300 300', role: 'img', 'aria-label': 'スキルのレーダーチャート' },
      [20, 40, 60, 80, 100].map((段) => s('polygon', {
        points: 軸名.map((_, i) => 点(i, 段).join(',')).join(' '),
        fill: 'none', stroke: 'var(--罫線)', 'stroke-width': 1,
      })),
      軸名.map((名前, i) => {
        const [x, y] = 点(i, 100);
        const [lx, ly] = 点(i, 122);
        return s('g', {},
          s('line', { x1: 中心, y1: 中心, x2: x, y2: y, stroke: 'var(--罫線)' }),
          s('text', { x: lx, y: ly + 4, 'text-anchor': 'middle', class: '軸名' }, 名前));
      }),
      系列.map((系) => {
        if (!系.値.some((v) => v !== null && v !== undefined)) return null;
        const 座標 = 系.値.map((v, i) => 点(i, v ?? 0));
        return s('g', {},
          s('polygon', { points: 座標.map((p) => p.join(',')).join(' '), fill: 系.色, 'fill-opacity': 系.塗り ?? 0.15, stroke: 系.色, 'stroke-width': 2.5, 'stroke-dasharray': 系.破線 ? '5 4' : null }),
          座標.map(([x, y], i) => (系.値[i] === null || 系.値[i] === undefined ? null : s('circle', { cx: x, cy: y, r: 3.5, fill: 系.色 }))));
      })),
    h('figcaption', { class: '凡例' }, 系列.map((系) => h('span', {}, h('i', { style: { background: 系.色 } }), 系.名前))));
}

// 系列 [{名前, 値: [...], 色}]、ラベル [...]
export function 折れ線グラフ(ラベル, 系列, { 単位 = '' } = {}) {
  const 幅 = 340;
  const 高さ = 180;
  const 余白 = { 左: 30, 右: 10, 上: 12, 下: 28 };
  const 全値 = 系列.flatMap((系) => 系.値).filter((v) => v !== null && v !== undefined);
  if (!全値.length) return h('p', { class: '空' }, 'まだ記録がありません');
  const 最大 = Math.max(10, Math.ceil(Math.max(...全値) / 5) * 5);
  const x = (i) => 余白.左 + (ラベル.length === 1 ? (幅 - 余白.左 - 余白.右) / 2 : (i * (幅 - 余白.左 - 余白.右)) / (ラベル.length - 1));
  const y = (v) => 余白.上 + (高さ - 余白.上 - 余白.下) * (1 - v / 最大);
  const 目盛 = [0, 最大 / 2, 最大];
  const 間引き = Math.ceil(ラベル.length / 6);
  return h('figure', { class: '折れ線' },
    s('svg', { viewBox: `0 0 ${幅} ${高さ}`, role: 'img', 'aria-label': '推移グラフ' },
      目盛.map((v) => s('g', {},
        s('line', { x1: 余白.左, x2: 幅 - 余白.右, y1: y(v), y2: y(v), stroke: 'var(--罫線)' }),
        s('text', { x: 余白.左 - 4, y: y(v) + 4, 'text-anchor': 'end', class: '目盛' }, `${v}${単位}`))),
      ラベル.map((名前, i) => (i % 間引き === 0 || i === ラベル.length - 1
        ? s('text', { x: x(i), y: 高さ - 8, 'text-anchor': 'middle', class: '目盛' }, 名前) : null)),
      系列.map((系) => {
        const 点 = 系.値.map((v, i) => (v === null || v === undefined ? null : [x(i), y(v)])).filter(Boolean);
        return s('g', {},
          s('polyline', { points: 点.map((p) => p.join(',')).join(' '), fill: 'none', stroke: 系.色, 'stroke-width': 2.5, 'stroke-linejoin': 'round' }),
          点.map(([px, py]) => s('circle', { cx: px, cy: py, r: 3.5, fill: 系.色 })));
      })),
    h('figcaption', { class: '凡例' }, 系列.map((系) => h('span', {}, h('i', { style: { background: 系.色 } }), 系.名前))));
}

// 成長記録カレンダー（月）。日をタップすると 選択時(日データ)
export function 月カレンダー(データ, 選択時) {
  const マス = [];
  const 月曜始まりの空き = データ.first_weekday; // 0=月曜
  for (let i = 0; i < 月曜始まりの空き; i++) マス.push(h('div', { class: '日 空き' }));
  const 今日 = new Date();
  for (const 日 of データ.days) {
    const d = 日付を読む(日.date);
    const 今日か = d.toDateString() === 今日.toDateString();
    const 印 = [
      日.attended.length ? h('i', { class: '印 練習', title: '練習参加' }) : null,
      日.steps.length ? h('i', { class: `印 ステップ ${日.steps.some((x) => x.cleared) ? 'クリア' : ''}`, title: 'ステップ練習' }) : null,
      日.self_practice.length ? h('i', { class: '印 自主練', title: '自主練' }) : null,
    ];
    マス.push(h('button', {
      class: `日 活動${日.level} ${今日か ? '今日' : ''}`,
      'aria-label': `${d.getMonth() + 1}月${d.getDate()}日 活動${日.level}`,
      onclick: () => 選択時?.(日),
    }, h('span', { class: '日付数字' }, d.getDate()), h('span', { class: '印列' }, 印)));
  }
  return h('div', { class: '月カレンダー' },
    ['月', '火', '水', '木', '金', '土', '日'].map((w) => h('div', { class: '曜日' }, w)),
    マス);
}

export function 進捗バー(値, 最大 = 100, 色 = null) {
  const 割合 = 最大 ? Math.max(0, Math.min(100, (値 / 最大) * 100)) : 0;
  return h('div', { class: '進捗バー', role: 'progressbar', 'aria-valuenow': String(値), 'aria-valuemax': String(最大) },
    h('div', { class: '進捗中身', style: { width: `${割合}%`, background: 色 || undefined } }));
}
