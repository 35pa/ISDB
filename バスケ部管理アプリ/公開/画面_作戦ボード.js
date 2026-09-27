// 作戦ボード：戦術図の一覧・閲覧（コマ送り／再生）・作成／編集、画像・PDF 出力、理解度チェック（クイズ・コメント・実技チェック）

import {
  api, 置き換え, h, s, 描画, 見出し, コーチか, 日時表示, 日付表示, 今日の日付, バッジ, 空表示, 通知, エラー通知, 確認, シート, フォーム, タブ, オフライン注記, 状態,
} from './共通.js';
import { コートの線, コート } from './図表.js';

// 画像として書き出しても色が崩れないよう、ボードは固定の配色で描く
const 配色 = {
  コート: '#f3dcb5', 線: '#ffffff', リング: '#ea580c', 味方: '#1d4ed8', 相手: '#dc2626', 矢印: '#1f2937', ボール: '#f97316', 文字: '#ffffff',
};
const 線の名前 = { move: '移動', dribble: 'ドリブル', pass: 'パス', screen: 'スクリーン' };
const 理解度 = ['よく分からない', 'だいたい分かった', '理解した'];
const 理解度の色 = ['悪', '注意', '良'];
// 理解度クイズの種類（並びは出題の順：形→基本→次の動き→移動先）
const 問題の種類 = [['位置', '位置タップ'], ['選択', '基本'], ['次の動き', '次の動き'], ['移動先', '移動先タップ']];
const 種類の名前 = Object.fromEntries(問題の種類);
const タップ問題 = (q) => q.quiz_type === '移動先' || q.quiz_type === '位置';
const できばえ = ['できなかった', '一部できた', '5人でそろってできた'];
const できばえの色 = ['悪', '注意', '良'];
const 正解の色 = '#16a34a';
let 一覧の絞り込み = 'すべて';
let テンプレートの分類 = 'すべて';
let クイズの絞り込み = 'すべて';

// 図の選手ID → 呼び名（O3 → 3番、X4 → X4）
function 選手名(id) {
  return id.startsWith('O') ? `${id.slice(1)}番` : id;
}

function 位置の一覧(位置) {
  return (位置 || '').split(',').filter(Boolean);
}

// タイトル先頭の【】を分類として扱う（例：【セットプレー】ピック&ロール）
function 分類(戦術) {
  return 戦術.title.match(/^【([^】]+)】/)?.[1] || 'その他';
}

// ---------- 描画 ----------

function 波線(点) {
  // ドリブルはジグザグの線で表す
  const 結果 = [];
  let 交互 = 1;
  for (let i = 0; i < 点.length - 1; i++) {
    const [x1, y1] = 点[i];
    const [x2, y2] = 点[i + 1];
    const 長さ = Math.hypot(x2 - x1, y2 - y1);
    const 分割 = Math.max(1, Math.floor(長さ / 12));
    const nx = -(y2 - y1) / (長さ || 1);
    const ny = (x2 - x1) / (長さ || 1);
    for (let k = 0; k < 分割; k++) {
      const t = k / 分割;
      const 最後の区間 = i === 点.length - 2 && k >= 分割 - 1;
      const 振れ = 最後の区間 ? 0 : 6 * 交互;
      結果.push([x1 + (x2 - x1) * t + nx * 振れ, y1 + (y2 - y1) * t + ny * 振れ]);
      交互 *= -1;
    }
  }
  結果.push(点[点.length - 1]);
  return 結果;
}

function 線を描く(線, { 選択時 = null } = {}) {
  const 点 = 線.points;
  if (点.length < 2) return null;
  const 共通 = { fill: 'none', stroke: 配色.矢印, 'stroke-width': 3, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' };
  const 押せる = 選択時 ? { onpointerdown: (e) => { e.stopPropagation(); 選択時(); }, class: '線 押せる' } : { class: '線' };
  if (線.type === 'screen') {
    const [x1, y1] = 点[点.length - 2];
    const [x2, y2] = 点[点.length - 1];
    const 長さ = Math.hypot(x2 - x1, y2 - y1) || 1;
    const nx = (-(y2 - y1) / 長さ) * 14;
    const ny = ((x2 - x1) / 長さ) * 14;
    return s('g', 押せる,
      s('polyline', { points: 点.map((p) => p.join(',')).join(' '), ...共通 }),
      s('line', { x1: x2 - nx, y1: y2 - ny, x2: x2 + nx, y2: y2 + ny, ...共通, 'stroke-width': 4 }),
      選択時 ? s('polyline', { points: 点.map((p) => p.join(',')).join(' '), fill: 'none', stroke: 'transparent', 'stroke-width': 18 }) : null);
  }
  const 表示点 = 線.type === 'dribble' ? 波線(点) : 線.type === 'pass' ? [点[0], 点[点.length - 1]] : 点;
  return s('g', 押せる,
    s('polyline', {
      points: 表示点.map((p) => p.join(',')).join(' '), ...共通,
      'stroke-dasharray': 線.type === 'pass' ? '10 7' : null, 'marker-end': 'url(#board-arrow)',
    }),
    選択時 ? s('polyline', { points: 点.map((p) => p.join(',')).join(' '), fill: 'none', stroke: 'transparent', 'stroke-width': 18 }) : null);
}

function 選手を描く(p, ボール保持, { 押下 = null, 強調 = false, 薄く = false } = {}) {
  const 味方 = p.team === 'O';
  return s('g', {
    class: `選手駒 ${押下 ? '動かせる' : ''}`, transform: `translate(${p.x} ${p.y})`, 'data-id': p.id,
    onpointerdown: 押下 ? (e) => 押下(e, p) : null, opacity: 薄く ? 0.75 : null,
  },
  押下 ? s('circle', { r: 26, fill: 'transparent' }) : null,
  強調 ? s('circle', { r: 24, fill: 'none', stroke: '#facc15', 'stroke-width': 5 }) : null,
  味方
    ? s('circle', { r: 16, fill: 配色.味方, stroke: '#fff', 'stroke-width': 2 })
    : s('g', {}, s('circle', { r: 16, fill: '#fff', stroke: 配色.相手, 'stroke-width': 3 })),
  s('text', { 'text-anchor': 'middle', y: 6, 'font-size': 17, 'font-weight': 700, 'font-family': 'sans-serif', fill: 味方 ? 配色.文字 : 配色.相手 }, 味方 ? p.label : `X${p.label}`),
  ボール保持 ? s('circle', { cx: 13, cy: -13, r: 7, fill: 配色.ボール, stroke: '#7c2d12', 'stroke-width': 1.5 }) : null);
}

// 画面上のタップ位置を図の座標（横500×縦470）に直す
function SVG座標(svg, e) {
  const 点 = svg.createSVGPoint();
  点.x = e.clientX;
  点.y = e.clientY;
  const p = 点.matrixTransform(svg.getScreenCTM().inverse());
  return [Math.round(Math.max(0, Math.min(コート.幅, p.x))), Math.round(Math.max(0, Math.min(コート.奥行, p.y)))];
}

// 重ね：最後に重ねて描く SVG 要素（正解の円など）、強調：黄色の輪で囲む選手ID、タップ：図をタップしたとき (座標) => {}
export function ボードSVG(コマ, { 編集 = null, クラス = '', 重ね = [], 強調 = null, タップ = null } = {}) {
  return s('svg', {
    viewBox: `0 0 ${コート.幅} ${コート.奥行}`, class: `作戦ボード ${クラス} ${タップ ? 'タップできる' : ''}`, role: 'img', 'aria-label': '作戦ボード',
    onpointerdown: 編集?.背景押下, onpointermove: 編集?.移動, onpointerup: 編集?.離す, onpointercancel: 編集?.離す,
    onclick: タップ ? (e) => タップ(SVG座標(e.currentTarget, e)) : null,
  },
  s('defs', {}, s('marker', { id: 'board-arrow', viewBox: '0 0 10 10', refX: 8, refY: 5, markerWidth: 5, markerHeight: 5, orient: 'auto-start-reverse' },
    s('path', { d: 'M 0 0 L 10 5 L 0 10 z', fill: 配色.矢印 }))),
  s('rect', { x: 0, y: 0, width: コート.幅, height: コート.奥行, fill: 配色.コート }),
  コートの線(配色.線, 配色.リング),
  s('g', { class: '線の層' }, (コマ.lines || []).map((線, i) => 線を描く(線, { 選択時: 編集?.線を選ぶ ? () => 編集.線を選ぶ(i) : null }))),
  編集?.描画中の線 ? 線を描く(編集.描画中の線) : null,
  s('g', { class: '選手の層' }, (コマ.players || []).map((p) => 選手を描く(p, コマ.ball === p.id, { 押下: 編集?.選手押下, 強調: p.id === 強調 }))),
  s('g', { class: '重ねの層' }, 重ね));
}

// ---------- 書き出し（画像・PDF・共有） ----------

function SVGを画像に(svg, 幅, 高さ) {
  return new Promise((解決, 失敗) => {
    const 文字列 = new XMLSerializer().serializeToString(svg);
    const 画像 = new Image();
    画像.onload = () => 解決(画像);
    画像.onerror = () => 失敗(new Error('画像を作れませんでした'));
    画像.width = 幅;
    画像.height = 高さ;
    画像.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(文字列)}`;
  });
}

function 折り返し(文脈, 文字, 最大幅) {
  const 行 = [];
  let 今 = '';
  for (const c of 文字) {
    if (文脈.measureText(今 + c).width > 最大幅) { 行.push(今); 今 = c; } else 今 += c;
  }
  if (今) 行.push(今);
  return 行;
}

// 全コマを縦に並べた1枚の PNG を作る
export async function 戦術画像を作る(戦術, コマ番号 = null) {
  const 対象 = コマ番号 === null ? 戦術.data.frames : [戦術.data.frames[コマ番号]];
  const 倍率 = 2;
  const 幅 = コート.幅 * 倍率;
  const 見出し高 = 90;
  const 注記高 = 80;
  const キャンバス = document.createElement('canvas');
  キャンバス.width = 幅;
  キャンバス.height = 見出し高 + 対象.length * (コート.奥行 * 倍率 + 注記高);
  const c = キャンバス.getContext('2d');
  c.fillStyle = '#ffffff';
  c.fillRect(0, 0, キャンバス.width, キャンバス.height);
  c.fillStyle = '#111827';
  c.font = 'bold 40px sans-serif';
  c.fillText(戦術.title, 24, 56);
  c.font = '24px sans-serif';
  c.fillStyle = '#6b7280';
  c.fillText(`${戦術.kind}${状態.チーム ? ` ・ ${状態.チーム.name}` : ''}`, 24, 84);
  let y = 見出し高;
  for (const [i, コマ] of 対象.entries()) {
    const svg = ボードSVG(コマ);
    svg.setAttribute('width', 幅);
    svg.setAttribute('height', コート.奥行 * 倍率);
    const 画像 = await SVGを画像に(svg, 幅, コート.奥行 * 倍率);
    c.drawImage(画像, 0, y, 幅, コート.奥行 * 倍率);
    c.fillStyle = '#111827';
    c.font = 'bold 26px sans-serif';
    const 番号 = コマ番号 === null ? i + 1 : コマ番号 + 1;
    c.fillText(`${番号}／${戦術.data.frames.length}`, 24, y + コート.奥行 * 倍率 + 34);
    c.font = '24px sans-serif';
    折り返し(c, コマ.note || '', 幅 - 140).slice(0, 2).forEach((行, k) => c.fillText(行, 110, y + コート.奥行 * 倍率 + 34 + k * 30));
    y += コート.奥行 * 倍率 + 注記高;
  }
  return new Promise((解決) => キャンバス.toBlob(解決, 'image/png'));
}

async function 画像を保存(戦術, コマ番号 = null) {
  try {
    const blob = await 戦術画像を作る(戦術, コマ番号);
    const ファイル名 = `${戦術.title}.png`;
    const ファイル = new File([blob], ファイル名, { type: 'image/png' });
    if (navigator.canShare?.({ files: [ファイル] })) {
      try {
        await navigator.share({ files: [ファイル], title: 戦術.title, text: `${戦術.title}（${戦術.kind}）` });
        return;
      } catch (e) {
        if (e.name === 'AbortError') return;
      }
    }
    const a = h('a', { href: URL.createObjectURL(blob), download: ファイル名 });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  } catch (エラー) { エラー通知(エラー); }
}

function PDFで出力(戦術) {
  // 印刷用の要素を作ってブラウザの印刷（「PDFに保存」）を使う
  const 印刷 = h('div', { id: '印刷領域' },
    h('h1', {}, 戦術.title),
    h('p', {}, `${戦術.kind}${状態.チーム ? ` ・ ${状態.チーム.name}` : ''}`),
    戦術.description ? h('p', { class: '本文' }, 戦術.description) : null,
    h('div', { class: '印刷コマ一覧' }, 戦術.data.frames.map((コマ, i) => h('figure', {},
      ボードSVG(コマ),
      h('figcaption', {}, h('strong', {}, `${i + 1}／${戦術.data.frames.length} `), コマ.note || '')))));
  document.getElementById('印刷領域')?.remove();
  document.body.append(印刷);
  document.body.classList.add('印刷中');
  const 後片付け = () => { document.body.classList.remove('印刷中'); 印刷.remove(); window.removeEventListener('afterprint', 後片付け); };
  window.addEventListener('afterprint', 後片付け);
  setTimeout(() => window.print(), 50);
}

// ---------- 一覧 ----------

export async function 戦術一覧画面() {
  const 戦術 = await api('GET', '/api/tactics');
  const 絞り込み = 一覧の絞り込み;
  const 分類一覧 = [...new Set(戦術.filter((t) => t.is_template).map(分類))];
  if (!分類一覧.includes(テンプレートの分類)) テンプレートの分類 = 'すべて';
  const 対象 = 戦術.filter((t) => (絞り込み === 'すべて' ? !t.is_template || コーチか()
    : 絞り込み === 'テンプレート' ? t.is_template && (テンプレートの分類 === 'すべて' || 分類(t) === テンプレートの分類)
      : t.kind === 絞り込み && !t.is_template));
  const 新規作成 = async () => {
    const テンプレート = 戦術.filter((t) => t.is_template);
    const 選択 = await シート('新しい戦術', (閉じる) => [
      h('button', { class: 'ボタン 大', onclick: () => 閉じる('空') }, '白紙から作る'),
      テンプレート.length ? h('h3', { class: 'フォーム小見出し' }, 'テンプレートから作る') : null,
      分類一覧.map((名前) => [
        h('h4', { class: 'テンプレート分類' }, 名前),
        h('div', { class: 'リスト' }, テンプレート.filter((t) => 分類(t) === 名前).map((t) => h('button', { class: 'リスト項目', onclick: () => 閉じる(t.id) },
          h('div', { class: 'ミニボード' }, ボードSVG(t.data.frames[0])),
          h('div', { class: '伸びる' }, h('strong', {}, t.title), h('small', {}, `${t.kind} ・ ${t.data.frames.length}コマ`))))),
      ]),
    ]);
    if (選択 === '空') location.hash = '#/tactics/new';
    else if (選択) {
      try {
        const 結果 = await api('POST', `/api/tactics/${選択}/copy`, {});
        location.hash = `#/tactics/${結果.id}/edit`;
      } catch (エラー) { エラー通知(エラー); }
    }
  };
  描画(
    見出し('作戦ボード', コーチか() ? h('button', { class: 'ボタン 小', onclick: 新規作成 }, '＋ 作成') : null),
    オフライン注記(戦術),
    タブ([['すべて', 'すべて'], ['オフェンス', 'オフェンス'], ['ディフェンス', 'ディフェンス'], ['テンプレート', 'テンプレ']], 絞り込み, (v) => { 一覧の絞り込み = v; 戦術一覧画面(); }),
    絞り込み === 'テンプレート' && 分類一覧.length > 1 ? h('div', { class: '分類タブ' },
      タブ([['すべて', 'すべて'], ...分類一覧.map((名前) => [名前, 名前])], テンプレートの分類, (v) => { テンプレートの分類 = v; 戦術一覧画面(); })) : null,
    対象.length ? h('div', { class: '戦術一覧' }, 対象.map((t) => h('a', { class: 'カード 戦術カード', href: `#/tactics/${t.id}` },
      h('div', { class: 'ミニボード' }, ボードSVG(t.data.frames[0])),
      h('div', { class: '伸びる' },
        h('strong', {}, t.title),
        h('div', { class: 'バッジ列' },
          バッジ(t.kind, t.kind === 'オフェンス' ? '味方' : '相手'),
          t.is_template ? バッジ('テンプレート', '薄') : null,
          t.published ? null : バッジ('非公開', '注意'),
          h('small', {}, `${t.data.frames.length}コマ`)),
        コーチか()
          ? h('small', {}, `理解した ${t.understood_count}人${t.practice_count ? ` ・ 実技チェック ${t.practice_count}回` : ''}`)
          : h('div', { class: 'バッジ列' },
            t.my_understood === null ? バッジ('未確認', '強調') : バッジ(理解度[t.my_understood], 理解度の色[t.my_understood]),
            t.my_practice_rating === null ? null : バッジ(`実技${t.my_practice_ok && t.my_practice_rating === 2 ? '◯' : '△'}`, t.my_practice_ok && t.my_practice_rating === 2 ? '良' : '注意'),
            t.quiz_count ? h('small', {}, `クイズ ${t.my_correct}/${t.quiz_count} 正解`) : null)))))
      : 空表示(絞り込み === 'テンプレート' ? 'テンプレートはありません' : 'まだ戦術がありません'),
    h('p', { class: '補足' }, '戦術図は一度開くとオフラインでも見られます'));
}

// ---------- 詳細（閲覧・理解度チェック） ----------

function 再生ビューア(戦術) {
  const コマ一覧 = 戦術.data.frames;
  let 現在 = 0;
  let 再生中 = false;
  const 盤 = h('div', { class: 'ボード枠' });
  const 番号 = h('span', { class: 'コマ番号' });
  const 注記 = h('p', { class: 'コマ注記' });
  const 再生ボタン = h('button', { class: 'ボタン', onclick: () => (再生中 ? 止める() : 再生()) }, '▶ 再生');
  const 表示 = (コマ) => {
    置き換え(盤, ボードSVG(コマ));
  };
  const 更新 = () => {
    表示(コマ一覧[現在]);
    番号.textContent = `${現在 + 1} ／ ${コマ一覧.length}`;
    注記.textContent = コマ一覧[現在].note || '';
  };
  const 移動アニメ = (元, 先) => new Promise((解決) => {
    const 開始 = performance.now();
    const 時間 = 1100;
    const 先の位置 = Object.fromEntries(先.players.map((p) => [p.id, p]));
    const 進める = (今) => {
      if (!再生中) return 解決();
      const t = Math.min(1, (今 - 開始) / 時間);
      const e = t < 0.5 ? 2 * t * t : 1 - ((-2 * t + 2) ** 2) / 2;
      表示({
        ...元,
        ball: t < 0.6 ? 元.ball : 先.ball,
        players: 元.players.map((p) => {
          const q = 先の位置[p.id] || p;
          return { ...p, x: p.x + (q.x - p.x) * e, y: p.y + (q.y - p.y) * e };
        }),
      });
      if (t < 1) requestAnimationFrame(進める); else 解決();
    };
    requestAnimationFrame(進める);
  });
  const 待つ = (ms) => new Promise((r) => setTimeout(r, ms));
  const 再生 = async () => {
    再生中 = true;
    再生ボタン.textContent = '■ 停止';
    if (現在 >= コマ一覧.length - 1) { 現在 = 0; 更新(); await 待つ(700); }
    while (再生中 && 現在 < コマ一覧.length - 1) {
      await 待つ(900);
      if (!再生中) break;
      await 移動アニメ(コマ一覧[現在], コマ一覧[現在 + 1]);
      if (!再生中) break;
      現在 += 1;
      更新();
    }
    止める();
  };
  const 止める = () => {
    再生中 = false;
    再生ボタン.textContent = '▶ 再生';
    更新();
  };
  更新();
  return {
    要素: h('div', { class: 'ビューア' },
      盤,
      h('div', { class: 'コマ操作' },
        h('button', { class: 'ボタン 控えめ', 'aria-label': '前のコマ', onclick: () => { 止める(); 現在 = Math.max(0, 現在 - 1); 更新(); } }, '◀'),
        番号,
        h('button', { class: 'ボタン 控えめ', 'aria-label': '次のコマ', onclick: () => { 止める(); 現在 = Math.min(コマ一覧.length - 1, 現在 + 1); 更新(); } }, '▶'),
        コマ一覧.length > 1 ? 再生ボタン : null),
      注記),
    現在のコマ: () => 現在,
  };
}

// ---------- 理解度クイズ ----------

// 選手から始まる線（その選手の動き・パス・スクリーン）。サーバーの 戦術クイズ.選手の線 と同じ判定
function 自分の線か(線, 選手) {
  return Boolean(選手) && Math.hypot(線.points[0][0] - 選手.x, 線.points[0][1] - 選手.y) <= 30;
}

// 問題と一緒に見せるコマ。次の動き・移動先は対象の選手の線（答え）を隠し、位置は対象の選手ごと隠す
function 問題用のコマ(戦術, q) {
  const コマ = q.frame === null || q.frame === undefined ? null : 戦術.data.frames[q.frame];
  if (!コマ) return null;
  const 対象 = 位置の一覧(q.position)[0];
  const 選手 = コマ.players.find((p) => p.id === 対象);
  const 線 = (q.quiz_type === '次の動き' && !選手) ? [] : コマ.lines.filter((l) => !自分の線か(l, 選手));
  if (q.quiz_type === '選択') return コマ;
  if (q.quiz_type === '位置') {
    return { ...コマ, lines: 線, players: コマ.players.filter((p) => p.id !== 対象), ball: コマ.ball === 対象 ? null : コマ.ball };
  }
  return { ...コマ, lines: 線 };
}

// 選択肢の並びを問題ごとに混ぜる（いつも同じ番号が正解にならないように）。同じ問題はいつも同じ並び
function 並び順(q) {
  const 順 = q.choices.map((_, i) => i);
  let 種 = (q.id * 2654435761) % 4294967296;
  for (let i = 順.length - 1; i > 0; i--) {
    種 = (種 * 1103515245 + 12345) % 2147483648;
    const j = 種 % (i + 1);
    [順[i], 順[j]] = [順[j], 順[i]];
  }
  return 順;
}

function 正解の印(戦術, q, 目標) {
  // 正解の範囲（緑の円）と、正解の位置に立つ選手（半透明）
  const 対象 = 位置の一覧(q.position)[0];
  const コマ番号 = q.quiz_type === '移動先' ? q.frame + 1 : q.frame;
  const 元 = (戦術.data.frames[コマ番号] || 戦術.data.frames[q.frame])?.players.find((p) => p.id === 対象);
  return [
    s('circle', { cx: 目標.x, cy: 目標.y, r: 目標.r, fill: 'rgba(22, 163, 74, 0.22)', stroke: 正解の色, 'stroke-width': 3, 'stroke-dasharray': '9 6' }),
    元 ? 選手を描く({ ...元, x: 目標.x, y: 目標.y }, false, { 薄く: true }) : null,
  ];
}

function タップの印([x, y], 正解 = null) {
  const 色 = 正解 === null ? '#111827' : 正解 ? 正解の色 : '#dc2626';
  return s('g', { transform: `translate(${x} ${y})` },
    s('circle', { r: 11, fill: 色, stroke: '#fff', 'stroke-width': 3 }),
    s('path', { d: 'M -5 -5 L 5 5 M 5 -5 L -5 5', stroke: '#fff', 'stroke-width': 3, 'stroke-linecap': 'round' }));
}

function 結果を表示(結果欄, 正解, 解説, 追記 = '') {
  置き換え(結果欄,
    h('strong', { class: 正解 ? '良 文字' : '悪 文字' }, 正解 ? '⭕ 正解！' : `❌ 不正解${追記}`),
    解説 ? h('p', {}, 解説) : null);
}

function 選択問題(戦術, q, 結果欄, 回答後) {
  const 順 = 並び順(q);
  const ボタン = {};
  const 色を付ける = (選んだ, 正解) => Object.entries(ボタン).forEach(([i, b]) => {
    b.classList.toggle('選んだ', Number(i) === 選んだ);
    b.classList.toggle('正解', Number(i) === 正解);
  });
  for (const i of 順) {
    ボタン[i] = h('button', {
      class: '選択肢',
      onclick: async () => {
        try {
          const r = await api('POST', `/api/quizzes/${q.id}/answer`, { choice: i });
          色を付ける(i, r.answer_index);
          結果を表示(結果欄, r.correct, r.explanation);
          回答後(r.correct);
        } catch (エラー) { エラー通知(エラー); }
      },
    }, q.choices[i]);
  }
  if (q.my_choice !== null) {
    色を付ける(q.my_choice, q.answer_index);
    結果を表示(結果欄, q.my_correct, q.explanation, '（もう一度選べます）');
  }
  const コマ = 問題用のコマ(戦術, q);
  return [
    コマ ? h('figure', { class: 'クイズ図' },
      h('div', { class: 'ボード枠 クイズ盤' }, ボードSVG(コマ, { 強調: q.quiz_type === '次の動き' ? 位置の一覧(q.position)[0] : null })),
      h('figcaption', {}, q.quiz_type === '次の動き' ? `コマ${q.frame + 1}で止めています（黄色の輪＝問題の選手）` : `コマ${q.frame + 1}`)) : null,
    h('div', { class: '選択肢列' }, 順.map((i) => ボタン[i])),
    コーチか() ? h('small', {}, `正解：${q.choices[q.answer_index]}`) : null,
  ];
}

function タップ問題の欄(戦術, q, 結果欄, 回答後) {
  const コマ = 問題用のコマ(戦術, q);
  if (!コマ) return h('p', { class: '補足' }, '図のコマが見つかりません（図が変更されました）');
  const 枠 = h('div', { class: 'ボード枠 クイズ盤' });
  const 対象 = 位置の一覧(q.position)[0];
  let 印 = q.my_tap ? [q.my_tap.x, q.my_tap.y] : null;
  let 目標 = q.target;
  let 答えた = q.my_tap !== null;
  let 正解 = q.my_correct;
  const 答える = h('button', {
    class: 'ボタン', disabled: true,
    onclick: async () => {
      try {
        const r = await api('POST', `/api/quizzes/${q.id}/answer`, { x: 印[0], y: 印[1] });
        答えた = true;
        正解 = r.correct;
        目標 = r.target;
        結果を表示(結果欄, r.correct, r.explanation);
        回答後(r.correct);
        更新();
      } catch (エラー) { エラー通知(エラー); }
    },
  }, 'ここで答える');
  const もう一度 = h('button', {
    class: 'ボタン 控えめ',
    onclick: () => { 答えた = false; 印 = null; 正解 = null; 置き換え(結果欄); 更新(); },
  }, 'もう一度');
  const 案内 = h('small', { class: 'ブロック' });
  function 更新() {
    const 重ね = [];
    if (目標 && (答えた || コーチか())) 重ね.push(...正解の印(戦術, q, 目標));
    if (印) 重ね.push(タップの印(印, 答えた ? 正解 : null));
    置き換え(枠, ボードSVG(コマ, {
      強調: q.quiz_type === '移動先' ? 対象 : null,
      重ね,
      タップ: 答えた ? null : (点) => { 印 = 点; 答える.disabled = false; 更新(); },
    }));
    答える.hidden = 答えた;
    答える.disabled = !印;
    もう一度.hidden = !答えた;
    案内.textContent = 答えた ? '緑の円＝正解の範囲' : 印 ? '位置がよければ「ここで答える」。タップし直すと動かせます' : '図をタップして答えよう';
  }
  更新();
  if (答えた) 結果を表示(結果欄, q.my_correct, q.explanation, '（もう一度答えられます）');
  return [
    h('figure', { class: 'クイズ図' }, 枠,
      h('figcaption', {}, `コマ${q.frame + 1}${q.quiz_type === '移動先' ? '（黄色の輪＝問題の選手）' : `（${選手名(対象)}を隠しています）`}`)),
    案内,
    h('div', { class: 'ボタン列' }, 答える, もう一度),
  ];
}

function クイズ欄(戦術) {
  const 位置 = [...new Set(戦術.quizzes.flatMap((q) => 位置の一覧(q.position)))]
    .sort((a, b) => a[0].localeCompare(b[0]) || Number(a.slice(1)) - Number(b.slice(1)));
  if (クイズの絞り込み !== 'すべて' && クイズの絞り込み !== '共通' && !位置.includes(クイズの絞り込み)) クイズの絞り込み = 'すべて';
  const 対象 = 戦術.quizzes
    .filter((q) => クイズの絞り込み === 'すべて' || (クイズの絞り込み === '共通' ? !q.position : 位置の一覧(q.position).includes(クイズの絞り込み)))
    .sort((a, b) => 問題の種類.findIndex(([k]) => k === a.quiz_type) - 問題の種類.findIndex(([k]) => k === b.quiz_type) || a.id - b.id);
  const 正解数 = new Map(戦術.quizzes.map((q) => [q.id, q.my_correct === true]));
  const 集計 = h('div', { class: 'クイズ集計' });
  const 集計を更新 = () => {
    置き換え(集計, ...問題の種類.map(([種類, 名前]) => {
      const 同じ = 対象.filter((q) => q.quiz_type === 種類);
      return 同じ.length ? h('span', {}, `${名前} `, h('strong', {}, `${同じ.filter((q) => 正解数.get(q.id)).length}/${同じ.length}`)) : null;
    }));
  };
  集計を更新();
  const 欄 = h('div', { class: 'クイズ一覧' });
  for (const [番号, q] of 対象.entries()) {
    const 結果欄 = h('div', { class: 'クイズ結果' });
    const 回答後 = (正解) => { 正解数.set(q.id, 正解); 集計を更新(); };
    欄.append(h('div', { class: 'クイズ' },
      h('div', { class: 'バッジ列' },
        バッジ(種類の名前[q.quiz_type] || '基本', タップ問題(q) ? '強調' : q.quiz_type === '次の動き' ? '注意' : '薄'),
        位置の一覧(q.position).length ? バッジ(`${位置の一覧(q.position).map(選手名).join('・')}向け`, 戦術.kind === 'オフェンス' ? '味方' : '相手') : null),
      h('p', { class: '問題' }, `Q${番号 + 1}. ${q.question}`),
      タップ問題(q) ? タップ問題の欄(戦術, q, 結果欄, 回答後) : 選択問題(戦術, q, 結果欄, 回答後),
      結果欄,
      コーチか() ? h('div', { class: 'ボタン列' },
        h('button', { class: 'ボタン 控えめ 小', onclick: () => クイズ編集(戦術, q) }, '編集'),
        h('button', {
          class: 'ボタン 控えめ 小',
          onclick: async () => {
            if (!(await 確認('このクイズを削除しますか？', '削除', true))) return;
            try { await api('DELETE', `/api/quizzes/${q.id}`); 戦術詳細画面(戦術.id); } catch (エラー) { エラー通知(エラー); }
          },
        }, '削除')) : null));
  }
  return h('div', {},
    位置.length ? h('div', { class: '分類タブ' },
      h('small', { class: 'ブロック' }, '自分のポジションを選ぶと、そのポジション向けの問題だけ出ます'),
      タブ([['すべて', 'すべて'], ['共通', '全員向け'], ...位置.map((p) => [p, 選手名(p)])], クイズの絞り込み, (v) => { クイズの絞り込み = v; 戦術詳細画面(戦術.id); })) : null,
    集計,
    対象.length ? 欄 : 空表示('このポジション向けの問題はありません'));
}

async function クイズ編集(戦術, q = null) {
  const コマ数 = 戦術.data.frames.length;
  const チーム = 戦術.kind === 'オフェンス' ? 'O' : 'X';
  const 選手ID = [...new Set(戦術.data.frames.flatMap((f) => f.players.map((p) => p.id)))]
    .sort((a, b) => (a[0] === チーム ? 0 : 1) - (b[0] === チーム ? 0 : 1) || a.localeCompare(b) || 0);
  const 値 = {
    quiz_type: q?.quiz_type || '選択', position: 位置の一覧(q?.position), frame: q?.frame ?? null,
    target: q?.target ? { ...q.target } : null,
  };
  const 保存 = await シート(q ? 'クイズを編集' : 'クイズを追加', (閉じる) => {
    const 項目 = (ラベル, 要素, 補足 = null) => h('div', { class: '項目' }, h('label', {}, ラベル), 要素, 補足 ? h('small', {}, 補足) : null);
    const 種類 = h('select', {}, [
      ['選択', '基本（選択肢から選ぶ）'], ['次の動き', '次の動き（コマを止めて選ぶ）'], ['移動先', '移動先タップ（動く先を図で答える）'], ['位置', '位置タップ（立つ位置を図で答える）'],
    ].map(([v, 名前]) => h('option', { value: v, selected: v === 値.quiz_type }, 名前)));
    const コマ = h('select', {}, [h('option', { value: '' }, 'なし'), ...戦術.data.frames.map((f, i) => h('option', { value: i, selected: 値.frame === i }, `コマ${i + 1}：${(f.note || '').slice(0, 20)}`))]);
    const 位置列 = h('div', { class: '位置列' }, 選手ID.map((id) => h('label', { class: '位置札' },
      h('input', { type: 'checkbox', value: id, checked: 値.position.includes(id) }), h('span', {}, 選手名(id)))));
    const 問題文 = h('textarea', { rows: 2, maxLength: 300, placeholder: '例：5番の次の動きは？' });
    問題文.value = q?.question || '';
    const 選択肢 = h('textarea', { rows: 4, placeholder: '1行に1つ（2〜5個）' });
    選択肢.value = q?.choices?.join('\n') || '';
    const 正解 = h('input', { type: 'number', min: 1, max: 5, inputMode: 'numeric', value: q && !タップ問題(q) ? q.answer_index + 1 : 1 });
    const 解説 = h('textarea', { rows: 2, maxLength: 1000, placeholder: '回答後に表示されます' });
    解説.value = q?.explanation || '';
    const 半径 = h('select', {}, [[35, '小（せまい）'], [50, 'ふつう'], [70, '大（広い）']].map(([r, 名前]) => h('option', { value: r, selected: (値.target?.r || 50) === r }, 名前)));
    const 盤 = h('div', { class: 'ボード枠 クイズ盤' });
    const 次の位置 = h('button', { type: 'button', class: 'ボタン 控えめ 小' }, '次のコマの位置を正解にする');
    const 選択欄 = h('div', {}, 項目('選択肢（1行に1つ、2〜5個）', 選択肢), 項目('正解は何番目？', 正解));
    const タップ欄 = h('div', {}, 項目('正解の位置（図をタップ）', 盤, '黄色の輪＝問題の選手。移動先は次のコマの位置、位置は隠した選手の位置が目安'), h('div', { class: 'ボタン列 折返し' }, 次の位置), 項目('正解の範囲', 半径));
    const 読む = () => {
      値.quiz_type = 種類.value;
      値.frame = コマ.value === '' ? null : Number(コマ.value);
      値.position = [...位置列.querySelectorAll('input:checked')].map((i) => i.value);
      if (値.target) 値.target.r = Number(半径.value);
    };
    const 対象の次の位置 = () => {
      const 対象 = 値.position[0];
      const コマ番号 = 値.quiz_type === '移動先' ? 値.frame + 1 : 値.frame;
      return 値.frame === null ? null : 戦術.data.frames[コマ番号]?.players.find((p) => p.id === 対象) || null;
    };
    const 更新 = () => {
      読む();
      const タップ = 値.quiz_type === '移動先' || 値.quiz_type === '位置';
      選択欄.hidden = タップ;
      タップ欄.hidden = !タップ;
      次の位置.textContent = 値.quiz_type === '移動先' ? '次のコマの位置を正解にする' : '隠した選手の位置を正解にする';
      次の位置.disabled = !対象の次の位置();
      const 見本 = 問題用のコマ(戦術, { ...値, position: 値.position.join(',') });
      置き換え(盤, 見本 ? ボードSVG(見本, {
        強調: 値.quiz_type === '移動先' ? 値.position[0] : null,
        重ね: 値.target ? 正解の印(戦術, { ...値, position: 値.position.join(',') }, 値.target) : [],
        タップ: ([x, y]) => { 値.target = { x, y, r: Number(半径.value) }; 更新(); },
      }) : h('p', { class: '補足' }, 'コマと対象の選手を選ぶと図が出ます'));
    };
    次の位置.onclick = () => { const p = 対象の次の位置(); if (p) { 値.target = { x: p.x, y: p.y, r: Number(半径.value) }; 更新(); } };
    [種類, コマ, 半径].forEach((e) => e.addEventListener('change', 更新));
    位置列.addEventListener('change', 更新);
    更新();
    const 送信 = h('button', { class: 'ボタン 大', type: 'button' }, '保存');
    送信.onclick = async () => {
      読む();
      const タップ = 値.quiz_type === '移動先' || 値.quiz_type === '位置';
      if (タップ && 値.position.length !== 1) return 通知('タップ問題は、問題の選手を1人だけ選んでください', 'エラー');
      const 本文 = {
        quiz_type: 値.quiz_type, position: 値.position, frame: 値.frame, question: 問題文.value.trim(), explanation: 解説.value.trim(),
        ...(タップ ? { target: 値.target } : { choices: 選択肢.value.split('\n').map((x) => x.trim()).filter(Boolean), answer_index: Number(正解.value) - 1 }),
      };
      送信.disabled = true;
      try {
        if (q) await api('PUT', `/api/quizzes/${q.id}`, 本文);
        else await api('POST', `/api/tactics/${戦術.id}/quizzes`, 本文);
        閉じる(true);
      } catch (エラー) { エラー通知(エラー); } finally { 送信.disabled = false; }
    };
    return h('div', { class: 'フォーム' },
      項目('問題の種類', 種類),
      項目('問題の選手（ポジション別）', 位置列, '選ぶと「その選手向け」の問題になります。何も選ばなければ全員向け'),
      項目(`一緒に見せるコマ（全${コマ数}コマ）`, コマ, '次の動き・タップ問題では必須。対象の選手の線（答え）は隠して見せます'),
      項目('問題', 問題文),
      選択欄, タップ欄,
      項目('解説（回答後に表示）', 解説),
      送信);
  });
  if (保存) { 通知('保存しました'); 戦術詳細画面(戦術.id); }
}

async function 移動先問題を自動作成(戦術) {
  if (!(await 確認('図のコマの間で大きく動いた選手ごとに「動く先をタップする問題」を作ります。同じコマ・同じ選手の問題があれば作りません。', '作成'))) return;
  try {
    const r = await api('POST', `/api/tactics/${戦術.id}/quizzes/auto`, {});
    通知(r.added ? `${r.added}問を作りました` : '新しく作れる問題はありませんでした（コマが1つだけ、または作成済み）', r.added ? '成功' : '注意');
    戦術詳細画面(戦術.id);
  } catch (エラー) { エラー通知(エラー); }
}

// ---------- 実技チェック（コートで5人がそろって動けたか） ----------

function 実技チェックの欄(戦術) {
  const コーチ = コーチか();
  return h('div', { class: 'リスト' }, 戦術.practices.map((記録) => h('div', { class: 'リスト項目 縦' },
    h('div', { class: '行 間' }, h('strong', {}, 日付表示(記録.checked_on, true)), バッジ(できばえ[記録.rating], できばえの色[記録.rating])),
    h('div', { class: 'コマ結果' }, 記録.frames_ok.slice(0, 戦術.data.frames.length).map((良, i) => h('span', { class: 良 ? '良 文字' : '悪 文字' }, `コマ${i + 1} ${良 ? '◯' : '×'}`))),
    h('div', { class: 'バッジ列' }, 記録.players.map((p) => バッジ(`${p.position ? `${選手名(p.position)} ` : ''}${p.name} ${p.ok ? '◯' : '×'}`, p.ok ? '良' : '悪'))),
    記録.note ? h('p', {}, 記録.note) : null,
    コーチ ? h('div', { class: 'ボタン列' }, h('button', {
      class: 'ボタン 控えめ 小',
      onclick: async () => {
        if (!(await 確認('この実技チェックの記録を削除しますか？', '削除', true))) return;
        try { await api('DELETE', `/api/practice/${記録.id}`); 戦術詳細画面(戦術.id); } catch (エラー) { エラー通知(エラー); }
      },
    }, '削除')) : null)));
}

async function 実技チェックを記録(戦術) {
  const チーム = 戦術.kind === 'オフェンス' ? 'O' : 'X';
  const 位置 = 戦術.data.frames[0].players.filter((p) => p.team === チーム).map((p) => p.id)
    .sort((a, b) => Number(a.slice(1)) - Number(b.slice(1)));
  const 選手 = 戦術.checks;
  const 保存 = await シート('実技チェックを記録', (閉じる) => {
    const 日 = h('input', { type: 'date', value: 今日の日付() });
    const 行 = 位置.map((id, i) => ({
      id,
      選手: h('select', {}, h('option', { value: '' }, '—'), 選手.map((p, k) => h('option', { value: p.id, selected: k === i }, `${p.number ? `#${p.number} ` : ''}${p.name}`))),
      良: h('input', { type: 'checkbox', checked: true }),
    }));
    const コマ = 戦術.data.frames.map(() => h('input', { type: 'checkbox', checked: true }));
    let 評価 = 2;
    const 評価ボタン = できばえ.map((名前, i) => h('button', { type: 'button', class: 'ボタン 控えめ', onclick: () => { 評価 = i; 色(); } }, 名前));
    const 色 = () => 評価ボタン.forEach((b, i) => { b.className = `ボタン ${i === 評価 ? できばえの色[i] : '控えめ'}`; });
    色();
    const メモ = h('textarea', { rows: 2, maxLength: 5000, placeholder: '例：3番のトップの埋めが遅い。声が出ていた' });
    const 送信 = h('button', { class: 'ボタン 大', type: 'button' }, '保存');
    送信.onclick = async () => {
      const 参加 = 行.filter((r) => r.選手.value).map((r) => ({ player_id: Number(r.選手.value), position: r.id, ok: r.良.checked }));
      if (!参加.length) return 通知('参加した選手を選んでください', 'エラー');
      送信.disabled = true;
      try {
        await api('POST', `/api/tactics/${戦術.id}/practice`, {
          checked_on: 日.value, rating: 評価, frames_ok: コマ.map((c) => c.checked), note: メモ.value.trim(), players: 参加,
        });
        閉じる(true);
      } catch (エラー) { エラー通知(エラー); } finally { 送信.disabled = false; }
    };
    return h('div', { class: 'フォーム' },
      h('div', { class: '項目' }, h('label', {}, '実施日'), 日),
      h('h3', { class: 'フォーム小見出し' }, 'ポジションと選手（できた人にチェック）'),
      h('div', { class: '表の枠' }, h('table', { class: '表 実技表' },
        h('tbody', {}, 行.map((r) => h('tr', {}, h('th', {}, 選手名(r.id)), h('td', {}, r.選手), h('td', {}, h('label', { class: 'チェック' }, r.良, ' できた'))))))),
      h('h3', { class: 'フォーム小見出し' }, 'コマごとに、5人がそろって動けたか'),
      h('div', { class: 'リスト' }, 戦術.data.frames.map((f, i) => h('label', { class: '項目 チェック' }, コマ[i], h('span', {}, `コマ${i + 1}：${f.note || ''}`)))),
      h('h3', { class: 'フォーム小見出し' }, '全体のできばえ'),
      h('div', { class: '出欠ボタン' }, 評価ボタン),
      h('div', { class: '項目' }, h('label', {}, 'メモ（選手にも見えます）'), メモ),
      送信);
  });
  if (保存) { 通知('記録しました'); 戦術詳細画面(戦術.id); }
}

// クイズ8割以上正解（全問回答）＋実技で本人も全体もできた
function 習得したか(戦術, c) {
  const 数 = 戦術.quizzes.length;
  const クイズ = !数 || (c.answered >= 数 && c.correct >= 数 * 0.8);
  return クイズ && c.practice_ok === true && c.practice_rating === 2;
}

export async function 戦術詳細画面(id) {
  const 戦術 = await api('GET', `/api/tactics/${id}`);
  const コーチ = コーチか();
  const ビューア = 再生ビューア(戦術);
  const コメント = h('textarea', { rows: 2, maxLength: 500, placeholder: '分からないところ・質問など（チーム内で共有されます）' });
  コメント.value = 戦術.my_check?.comment || '';
  const 理解度を送る = async (度合い) => {
    try {
      await api('PUT', `/api/tactics/${id}/check`, { understood: 度合い, comment: コメント.value });
      通知('送信しました');
      戦術詳細画面(id);
    } catch (エラー) { エラー通知(エラー); }
  };

  描画(
    見出し(戦術.title, コーチ ? h('a', { class: 'ボタン 小 控えめ', href: `#/tactics/${id}/edit` }, '編集') : null, '#/tactics'),
    オフライン注記(戦術),
    h('div', { class: 'バッジ列' }, バッジ(戦術.kind, 戦術.kind === 'オフェンス' ? '味方' : '相手'), 戦術.is_template ? バッジ('テンプレート', '薄') : null, 戦術.published ? null : バッジ('非公開（選手には見えません）', '注意')),
    戦術.description ? h('p', { class: '本文' }, 戦術.description) : null,
    ビューア.要素,
    h('div', { class: 'ボタン列 折返し' },
      h('button', { class: 'ボタン 控えめ 小', onclick: () => 画像を保存(戦術, ビューア.現在のコマ()) }, '🖼️ このコマを画像で'),
      h('button', { class: 'ボタン 控えめ 小', onclick: () => 画像を保存(戦術) }, '🖼️ 全コマを画像で'),
      h('button', { class: 'ボタン 控えめ 小', onclick: () => PDFで出力(戦術) }, '📄 PDF・印刷')),
    h('div', { class: '凡例' },
      h('span', {}, h('i', { style: { background: 配色.味方 } }), '味方'),
      h('span', {}, h('i', { style: { background: '#fff', border: `2px solid ${配色.相手}` } }), '相手'),
      h('span', {}, '── 移動'), h('span', {}, '〰 ドリブル'), h('span', {}, '- - パス'), h('span', {}, '─┤ スクリーン')),

    戦術.quizzes.length || コーチ ? h('section', { class: 'カード' },
      h('div', { class: '行 間' }, h('h2', {}, '📝 理解度クイズ'), コーチ ? h('button', { class: 'ボタン 小', onclick: () => クイズ編集(戦術) }, '＋ 追加') : null),
      h('p', { class: '補足' }, '基本・次の動き（コマを止めて選ぶ）・タップ（図で位置を答える）の3種類。ポジション別の問題もあります'),
      戦術.quizzes.length ? クイズ欄(戦術) : 空表示('クイズはまだありません'),
      コーチ && 戦術.data.frames.length > 1 ? h('div', { class: 'ボタン列' },
        h('button', { class: 'ボタン 控えめ 小', onclick: () => 移動先問題を自動作成(戦術) }, '🪄 図から移動先タップ問題を自動作成')) : null) : null,

    コーチ || 戦術.practices.length ? h('section', { class: 'カード' },
      h('div', { class: '行 間' }, h('h2', {}, '🏃 実技チェック'), コーチ ? h('button', { class: 'ボタン 小', onclick: () => 実技チェックを記録(戦術) }, '＋ 記録') : null),
      h('p', { class: '補足' }, コーチ
        ? 'コートで実際に動いて、5人がそろって図のとおりに動けたかを記録します（コマごと・選手ごと）'
        : 'コーチが記録した、あなたが参加した実技チェックの結果'),
      戦術.practices.length ? 実技チェックの欄(戦術) : 空表示('まだ記録はありません')) : null,

    h('section', { class: 'カード' },
      h('h2', {}, '✅ 理解度チェック'),
      h('p', { class: '補足' }, 'この戦術をどれくらい理解できたか教えてください'),
      h('div', { class: '出欠ボタン' }, 理解度.map((名前, i) => h('button', {
        class: `ボタン ${戦術.my_check?.understood === i ? 理解度の色[i] : '控えめ'}`, onclick: () => 理解度を送る(i),
      }, 名前))),
      コメント,
      戦術.my_check ? h('small', {}, `送信済み：${理解度[戦術.my_check.understood]}（${日時表示(戦術.my_check.updated_at)}）`) : null),

    戦術.comments.length ? h('section', { class: 'カード' },
      h('h2', {}, '💬 みんなのコメント'),
      h('div', { class: 'リスト' }, 戦術.comments.map((c) => h('div', { class: 'リスト項目 縦' },
        h('div', { class: '行 間' }, h('strong', {}, c.name), c.understood === null ? null : バッジ(理解度[c.understood], 理解度の色[c.understood])),
        h('p', {}, c.comment))))) : null,

    コーチ ? h('section', { class: 'カード' },
      h('h2', {}, '👥 選手の理解度'),
      h('div', { class: '表の枠' }, h('table', { class: '表 理解度表' },
        h('thead', {}, h('tr', {}, h('th', {}, '選手'), h('th', {}, '理解度'), h('th', {}, 'クイズ'))),
        h('tbody', {}, 戦術.checks.map((c) => h('tr', {},
          h('td', {}, 習得したか(戦術, c) ? '🏅 ' : '', c.number ? `#${c.number} ` : '', c.name),
          h('td', {}, c.understood === null ? バッジ('未確認', '薄') : バッジ(理解度[c.understood], 理解度の色[c.understood])),
          h('td', {}, 戦術.quizzes.length ? `${c.correct}/${戦術.quizzes.length}` : '—',
            c.practice_rating === null ? null : h('div', {}, バッジ(`実技${c.practice_ok ? '◯' : '×'}`, c.practice_ok && c.practice_rating === 2 ? '良' : c.practice_ok ? '注意' : '悪')))))))),
      h('small', { class: 'ブロック' }, '🏅＝習得（クイズを全問答えて8割以上正解＋実技チェックで本人も全体もできた）。実技は一番新しい記録')) : null,

    コーチ ? h('div', { class: 'ボタン列' },
      h('button', {
        class: 'ボタン 控えめ',
        onclick: async () => {
          try { const r = await api('POST', `/api/tactics/${id}/copy`, {}); 通知('コピーしました'); location.hash = `#/tactics/${r.id}/edit`; } catch (エラー) { エラー通知(エラー); }
        },
      }, '📄 コピーして新規作成'),
      h('button', {
        class: 'ボタン 危険',
        onclick: async () => {
          if (!(await 確認(`「${戦術.title}」を削除しますか？クイズと回答も消えます。`, '削除', true))) return;
          try { await api('DELETE', `/api/tactics/${id}`); 通知('削除しました'); location.hash = '#/tactics'; } catch (エラー) { エラー通知(エラー); }
        },
      }, '削除')) : null);
}

// ---------- 作成・編集 ----------

function 初期配置(ディフェンスも = true) {
  const 味方 = [[250, 330], [80, 230], [420, 230], [25, 60], [330, 150]];
  const 相手 = [[250, 290], [110, 200], [390, 200], [60, 80], [300, 110]];
  const players = 味方.map(([x, y], i) => ({ id: `O${i + 1}`, team: 'O', label: String(i + 1), x, y }));
  if (ディフェンスも) 相手.forEach(([x, y], i) => players.push({ id: `X${i + 1}`, team: 'X', label: String(i + 1), x, y }));
  return { frames: [{ players, ball: 'O1', lines: [], note: '' }] };
}

// 次のコマの初期状態：移動・ドリブル線の終点へ選手を進め、パスの先へボールを渡す
function 次のコマを作る(コマ) {
  const 選手 = コマ.players.map((p) => ({ ...p }));
  let ボール = コマ.ball;
  const 近い選手 = ([x, y], 候補 = 選手, 距離 = 30) => 候補.reduce((最良, p) => {
    const d = Math.hypot(p.x - x, p.y - y);
    return d < 距離 && (!最良 || d < 最良.d) ? { p, d } : 最良;
  }, null)?.p;
  const 動いた = new Set();
  for (const 線 of コマ.lines) {
    if (線.type !== 'move' && 線.type !== 'dribble') continue;
    const p = 近い選手(線.points[0], 選手.filter((q) => !動いた.has(q.id)));
    if (p) { [p.x, p.y] = 線.points[線.points.length - 1]; 動いた.add(p.id); }
  }
  for (const 線 of コマ.lines) {
    if (線.type !== 'pass') continue;
    const 受け手 = 近い選手(線.points[線.points.length - 1], 選手, 45);
    if (受け手) ボール = 受け手.id;
  }
  return { players: 選手, ball: ボール, lines: [], note: '' };
}

export async function 戦術編集画面(id) {
  const 元 = id ? await api('GET', `/api/tactics/${id}`) : null;
  const 図 = 元 ? structuredClone(元.data) : 初期配置();
  let 現在 = 0;
  let 道具 = '移動';
  let 操作 = null; // { 種類: 'ドラッグ' | '線', ... }
  const 履歴 = [];
  const 記録 = () => { 履歴.push(JSON.stringify(図)); if (履歴.length > 50) 履歴.shift(); };

  const 盤 = h('div', { class: 'ボード枠 編集中' });
  const コマ列 = h('div', { class: 'コマ列' });
  const 注記欄 = h('input', { type: 'text', maxLength: 300, placeholder: 'このコマの説明（例：5番がスクリーン）' });
  const 道具列 = h('div', { class: '道具列', role: 'toolbar' });

  const 座標 = (e) => SVG座標(盤.querySelector('svg'), e);
  const コマ = () => 図.frames[現在];

  const 編集操作 = {
    選手押下: (e, p) => {
      e.stopPropagation();
      if (道具 === 'ボール') { 記録(); コマ().ball = p.id; 再描画(); return; }
      if (道具 === '移動') {
        記録();
        操作 = { 種類: 'ドラッグ', id: p.id };
        e.currentTarget.ownerSVGElement.setPointerCapture?.(e.pointerId);
        return;
      }
      if (線の名前[道具]) 線を開始(e, [p.x, p.y]);
    },
    背景押下: (e) => {
      if (線の名前[道具]) 線を開始(e, 座標(e));
    },
    移動: (e) => {
      if (!操作) return;
      e.preventDefault();
      const [x, y] = 座標(e);
      if (操作.種類 === 'ドラッグ') {
        const p = コマ().players.find((q) => q.id === 操作.id);
        p.x = x;
        p.y = y;
        const g = 盤.querySelector(`g[data-id="${操作.id}"]`);
        g?.setAttribute('transform', `translate(${x} ${y})`);
      } else if (操作.種類 === '線') {
        const 最後 = 操作.線.points[操作.線.points.length - 1];
        if (Math.hypot(最後[0] - x, 最後[1] - y) > 10) {
          if (操作.線.type === 'pass' || 操作.線.type === 'screen') 操作.線.points = [操作.線.points[0], [x, y]];
          else 操作.線.points.push([x, y]);
          描き直し();
        }
      }
    },
    離す: () => {
      if (操作?.種類 === '線' && 操作.線.points.length >= 2) {
        記録();
        コマ().lines.push(操作.線);
      }
      const 終わった = 操作;
      操作 = null;
      編集操作.描画中の線 = null;
      if (終わった) 再描画();
    },
    線を選ぶ: (i) => {
      if (道具 !== '消す') return;
      記録();
      コマ().lines.splice(i, 1);
      再描画();
    },
    描画中の線: null,
  };
  function 線を開始(e, 始点) {
    操作 = { 種類: '線', 線: { type: 道具, points: [始点] } };
    編集操作.描画中の線 = 操作.線;
    盤.querySelector('svg')?.setPointerCapture?.(e.pointerId);
  }
  function 描き直し() {
    // 線を描いている途中は描画中の線だけ差し替える（ポインタのキャプチャを保つため SVG は作り直さない）
    const svg = 盤.querySelector('svg');
    svg.querySelector('.描画中')?.remove();
    const 線 = ボードSVG({ players: [], lines: [操作.線] }).querySelector('.線の層 > g');
    if (線) { 線.classList.add('描画中'); svg.querySelector('.選手の層').before(線); }
  }

  function 再描画() {
    置き換え(盤, ボードSVG(コマ(), { 編集: { ...編集操作, 線を選ぶ: 道具 === '消す' ? 編集操作.線を選ぶ : null } }));
    注記欄.value = コマ().note || '';
    置き換え(コマ列, 
      ...図.frames.map((_, i) => h('button', { class: `コマ札 ${i === 現在 ? '選択中' : ''}`, onclick: () => { 現在 = i; 再描画(); } }, i + 1)),
      h('button', {
        class: 'コマ札 追加', title: 'コマを追加', disabled: 図.frames.length >= 20,
        onclick: () => { 記録(); 図.frames.splice(現在 + 1, 0, 次のコマを作る(コマ())); 現在 += 1; 再描画(); 通知('線の先へ選手を進めた新しいコマを追加しました'); },
      }, '＋'));
    置き換え(道具列, 
      ...[['移動', '✋ 動かす'], ['move', '→ 移動線'], ['dribble', '〰 ドリブル'], ['pass', '⇢ パス'], ['screen', '┤ スクリーン'], ['ボール', '🏀 ボール'], ['消す', '🧽 線を消す']]
        .map(([値, 表示]) => h('button', { class: `道具 ${道具 === 値 ? '選択中' : ''}`, 'aria-pressed': String(道具 === 値), onclick: () => { 道具 = 値; 再描画(); } }, 表示)));
  }

  const 元に戻す = () => {
    if (!履歴.length) return;
    const 前 = JSON.parse(履歴.pop());
    図.frames = 前.frames;
    現在 = Math.min(現在, 図.frames.length - 1);
    再描画();
  };
  注記欄.addEventListener('change', () => { コマ().note = 注記欄.value; });

  const 相手の表示 = () => コマ().players.some((p) => p.team === 'X');
  const 相手を切り替え = () => {
    記録();
    const 表示する = !相手の表示();
    const 初期 = 初期配置(true).frames[0].players.filter((p) => p.team === 'X');
    for (const f of 図.frames) {
      f.players = 表示する ? [...f.players.filter((p) => p.team === 'O'), ...初期.map((p) => ({ ...p }))] : f.players.filter((p) => p.team === 'O');
      if (!f.players.some((p) => p.id === f.ball)) f.ball = null;
    }
    再描画();
  };

  再描画();
  const 情報 = フォーム([
    { 名前: 'title', ラベル: 'タイトル', 必須: true, 例: '例：ホーンズ・セット' },
    { 名前: 'kind', ラベル: '種別', 種類: 'select', 選択肢: ['オフェンス', 'ディフェンス'] },
    { 名前: 'description', ラベル: '説明・ポイント', 種類: 'textarea', 行数: 3 },
    { 名前: 'published', ラベル: '選手に公開する', 種類: 'checkbox' },
    { 名前: 'is_template', ラベル: 'テンプレートとして保存（他の戦術のひな形にする）', 種類: 'checkbox' },
  ], async (値) => {
    コマ().note = 注記欄.value;
    const 本文 = { ...値, data: 図 };
    const 結果 = id ? await api('PUT', `/api/tactics/${id}`, 本文) : await api('POST', '/api/tactics', 本文);
    通知('保存しました');
    location.hash = `#/tactics/${結果.id}`;
  }, { 値: 元 ? { ...元, published: Boolean(元.published), is_template: Boolean(元.is_template) } : { kind: 'オフェンス', published: true } });

  描画(
    見出し(id ? '戦術を編集' : '戦術を作成', null, id ? `#/tactics/${id}` : '#/tactics'),
    道具列,
    盤,
    h('div', { class: '行 間 コマ行' }, コマ列,
      h('div', { class: 'ボタン列' },
        h('button', { class: 'ボタン 控えめ 小', onclick: 元に戻す, 'aria-label': '元に戻す' }, '↶ 戻す'),
        h('button', {
          class: 'ボタン 控えめ 小',
          onclick: () => {
            if (図.frames.length <= 1) return 通知('最後の1コマは消せません', '注意');
            記録();
            図.frames.splice(現在, 1);
            現在 = Math.max(0, 現在 - 1);
            再描画();
          },
        }, 'コマ削除'))),
    注記欄,
    h('div', { class: 'ボタン列 折返し' },
      h('button', { class: 'ボタン 控えめ 小', onclick: 相手を切り替え }, '相手（X）の表示／非表示'),
      h('button', { class: 'ボタン 控えめ 小', onclick: () => { 記録(); コマ().lines = []; 再描画(); } }, 'このコマの線を全部消す')),
    h('details', { class: 'カード' }, h('summary', {}, '使い方'),
      h('ul', { class: '箇条' },
        h('li', {}, '「動かす」で選手をドラッグして配置'),
        h('li', {}, '線の道具を選び、選手や床から指でなぞって動きを描く'),
        h('li', {}, '「＋」でコマを追加すると、移動線の先に選手が進んだ状態の次のコマができる'),
        h('li', {}, '「ボール」で選手をタップするとボールを持たせられる'))),
    h('div', { class: 'カード' }, 情報));
}
