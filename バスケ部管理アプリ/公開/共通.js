// 画面共通の部品：API 呼び出し・DOM 作成・ダイアログ・通知・日付の表示

export const 状態 = {
  トークン: 読み出し('token') || '',
  ユーザー: JSON.parse(読み出し('user') || 'null'),
  チーム: JSON.parse(読み出し('team') || 'null'),
};

function 読み出し(キー) {
  try { return localStorage.getItem(キー); } catch { return null; }
}
function 書き込み(キー, 値) {
  try { 値 === null ? localStorage.removeItem(キー) : localStorage.setItem(キー, 値); } catch { /* 保存できない環境では無視 */ }
}

export function ログイン状態を保存(トークン, ユーザー, チーム) {
  状態.トークン = トークン ?? 状態.トークン;
  状態.ユーザー = ユーザー ?? 状態.ユーザー;
  状態.チーム = チーム ?? 状態.チーム;
  書き込み('token', 状態.トークン);
  書き込み('user', JSON.stringify(状態.ユーザー));
  書き込み('team', JSON.stringify(状態.チーム));
}

export function ログイン状態を消去() {
  状態.トークン = '';
  状態.ユーザー = null;
  状態.チーム = null;
  ['token', 'user', 'team'].forEach((k) => 書き込み(k, null));
  // 共有端末で前の人のデータが残らないよう、オフライン用に保存した API の結果も消す
  if (navigator.serviceWorker?.controller) navigator.serviceWorker.controller.postMessage('APIキャッシュ削除');
}

export const コーチか = () => 状態.ユーザー?.role === 'coach';

export class API失敗 extends Error {
  constructor(メッセージ, ステータス) { super(メッセージ); this.ステータス = ステータス; }
}

// 画面遷移の番号。遷移後に前の画面の読み込みが遅れて終わっても、新しい画面を上書きしないようにする
export const 遷移 = { 番号: 0 };
export class 遷移により中断 extends Error {}

export async function api(メソッド, パス, 本文) {
  const 開始時の遷移 = 遷移.番号;
  const 設定 = { method: メソッド, headers: {} };
  if (状態.トークン) 設定.headers.Authorization = `Bearer ${状態.トークン}`;
  if (本文 !== undefined) {
    設定.headers['Content-Type'] = 'application/json';
    設定.body = JSON.stringify(本文);
  }
  let 応答;
  try {
    応答 = await fetch(パス, 設定);
  } catch {
    throw new API失敗('通信できませんでした。電波の良い場所で再度お試しください', 0);
  }
  let データ = null;
  try { データ = await 応答.json(); } catch { /* 空の応答 */ }
  if (応答.headers.get('X-Offline-Cache') === '1' && データ) データ.__オフライン = true;
  if (メソッド === 'GET' && 開始時の遷移 !== 遷移.番号) throw new 遷移により中断('画面が切り替わりました');
  if (!応答.ok) {
    if (応答.status === 401 && 状態.トークン && パス !== '/api/login') {
      ログイン状態を消去();
      location.hash = '#/login';
    }
    throw new API失敗(データ?.error || `エラーが発生しました（${応答.status}）`, 応答.status);
  }
  return データ;
}

// ---------- DOM ----------

// h('div', {class: 'x', onclick: fn}, '文字', 子要素...) 文字列は textContent として入る（HTML は解釈しない）
export function h(タグ, 属性 = {}, ...子) {
  const 要素 = document.createElement(タグ);
  for (const [キー, 値] of Object.entries(属性 || {})) {
    if (値 === undefined || 値 === null || 値 === false) continue;
    if (キー.startsWith('on') && typeof 値 === 'function') 要素.addEventListener(キー.slice(2), 値);
    else if (キー === 'class') 要素.className = 値;
    else if (キー === 'style' && typeof 値 === 'object') Object.assign(要素.style, 値);
    else if (キー === 'dataset') Object.assign(要素.dataset, 値);
    else if (キー in 要素 && typeof 値 !== 'string') 要素[キー] = 値;
    else 要素.setAttribute(キー, 値 === true ? '' : 値);
  }
  追加(要素, 子);
  return 要素;
}

function 追加(親, 子) {
  for (const c of 子.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    親.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
}

const SVG名前空間 = 'http://www.w3.org/2000/svg';
export function s(タグ, 属性 = {}, ...子) {
  const 要素 = document.createElementNS(SVG名前空間, タグ);
  for (const [キー, 値] of Object.entries(属性 || {})) {
    if (値 === undefined || 値 === null || 値 === false) continue;
    if (キー.startsWith('on') && typeof 値 === 'function') 要素.addEventListener(キー.slice(2), 値);
    else 要素.setAttribute(キー, 値);
  }
  追加(要素, 子);
  return 要素;
}

// replaceChildren の代わり。null・false は無視し、配列は展開する
export function 置き換え(親, ...子) {
  親.replaceChildren();
  追加(親, 子);
}

export const 画面 = () => document.getElementById('画面');

export function 描画(...子) {
  const 領域 = 画面();
  領域.replaceChildren();
  追加(領域, 子);
  window.scrollTo(0, 0);
}

export function 見出し(タイトル, 右 = null, 戻る = null) {
  return h('header', { class: '画面見出し' },
    戻る ? h('a', { class: '戻る', href: 戻る, 'aria-label': '戻る' }, '‹') : null,
    h('h1', {}, タイトル),
    右 ? h('div', { class: '見出し右' }, 右) : null);
}

export function 読み込み中() {
  描画(h('div', { class: '読み込み' }, h('div', { class: 'くるくる' }), '読み込み中…'));
}

export function エラー表示(エラー) {
  描画(h('div', { class: 'カード エラー' },
    h('p', {}, エラー.message || String(エラー)),
    h('button', { class: 'ボタン', onclick: () => location.reload() }, '再読み込み')));
}

export function 空表示(文言) {
  return h('p', { class: '空' }, 文言);
}

export function オフライン注記(データ) {
  return データ?.__オフライン ? h('p', { class: 'オフライン注記' }, '📴 オフラインのため、前回保存した内容を表示しています') : null;
}

// ---------- 通知・ダイアログ ----------

export function 通知(文言, 種類 = '成功') {
  const 箱 = document.getElementById('通知');
  const 要素 = h('div', { class: `通知 ${種類}`, role: 'status' }, 文言);
  箱.append(要素);
  setTimeout(() => 要素.classList.add('消える'), 2600);
  setTimeout(() => 要素.remove(), 3000);
}

export function エラー通知(エラー) {
  通知(エラー.message || String(エラー), 'エラー');
}

// 下から出るシート。内容を返す関数に「閉じる」を渡す。Promise は閉じたときの値で解決する。
export function シート(タイトル, 内容を作る) {
  return new Promise((解決) => {
    const ダイアログ = h('dialog', { class: 'シート' });
    let 結果 = undefined;
    const 閉じる = (値) => { 結果 = 値; ダイアログ.close(); };
    ダイアログ.append(
      h('div', { class: 'シート見出し' },
        h('h2', {}, タイトル),
        h('button', { class: '閉じる', 'aria-label': '閉じる', onclick: () => 閉じる(undefined) }, '×')),
      h('div', { class: 'シート本文' }, 内容を作る(閉じる)));
    ダイアログ.addEventListener('close', () => { ダイアログ.remove(); 解決(結果); });
    ダイアログ.addEventListener('click', (e) => { if (e.target === ダイアログ) 閉じる(undefined); });
    document.body.append(ダイアログ);
    ダイアログ.showModal();
  });
}

export function 確認(文言, はい = 'OK', 危険 = false) {
  return シート('確認', (閉じる) => [
    h('p', {}, 文言),
    h('div', { class: 'ボタン列' },
      h('button', { class: 'ボタン 控えめ', onclick: () => 閉じる(false) }, 'キャンセル'),
      h('button', { class: `ボタン ${危険 ? '危険' : ''}`, onclick: () => 閉じる(true) }, はい)),
  ]).then((v) => v === true);
}

// ---------- フォーム ----------

// 項目定義 [{名前, ラベル, 種類: text|number|date|time|select|textarea|checkbox|range|url, 選択肢, 必須, 既定, 補足}]
export function フォーム(項目一覧, 送信, { 送信文言 = '保存', 値 = {} } = {}) {
  const フォーム要素 = h('form', { class: 'フォーム', novalidate: true });
  const 入力 = {};
  for (const 項目 of 項目一覧) {
    if (項目.種類 === '見出し') { フォーム要素.append(h('h3', { class: 'フォーム小見出し' }, 項目.ラベル)); continue; }
    const 初期値 = 値[項目.名前] ?? 項目.既定 ?? '';
    let 要素;
    const id = `入力-${項目.名前}-${Math.random().toString(36).slice(2, 7)}`;
    if (項目.種類 === 'select') {
      要素 = h('select', { id, name: 項目.名前 },
        (項目.選択肢 || []).map((c) => {
          const [v, 表示] = Array.isArray(c) ? c : [c, c];
          return h('option', { value: v, selected: String(v) === String(初期値) }, 表示);
        }));
    } else if (項目.種類 === 'textarea') {
      要素 = h('textarea', { id, name: 項目.名前, rows: 項目.行数 || 3, maxLength: 項目.最大 || 5000, placeholder: 項目.例 || '' });
      要素.value = 初期値;
    } else if (項目.種類 === 'checkbox') {
      要素 = h('input', { id, type: 'checkbox', name: 項目.名前, checked: Boolean(初期値) });
    } else {
      要素 = h('input', {
        id, name: 項目.名前, type: 項目.種類 || 'text', placeholder: 項目.例 || '',
        min: 項目.最小, max: 項目.最大値, step: 項目.刻み, maxLength: 項目.最大, inputMode: 項目.入力モード,
        autocomplete: 項目.自動補完 || 'off',
      });
      要素.value = 初期値;
    }
    入力[項目.名前] = 要素;
    if (項目.種類 === 'checkbox') {
      フォーム要素.append(h('label', { class: '項目 チェック', for: id }, 要素, h('span', {}, 項目.ラベル)));
    } else {
      フォーム要素.append(h('div', { class: '項目' },
        h('label', { for: id }, 項目.ラベル, 項目.必須 ? h('span', { class: '必須' }, '必須') : null),
        要素,
        項目.補足 ? h('small', {}, 項目.補足) : null));
    }
  }
  const ボタン = h('button', { class: 'ボタン 大', type: 'submit' }, 送信文言);
  フォーム要素.append(ボタン);
  フォーム要素.addEventListener('submit', async (e) => {
    e.preventDefault();
    const データ = {};
    for (const 項目 of 項目一覧) {
      const 要素 = 入力[項目.名前];
      if (!要素) continue;
      if (項目.種類 === 'checkbox') データ[項目.名前] = 要素.checked;
      else if (項目.種類 === 'number' || 項目.種類 === 'range') データ[項目.名前] = 要素.value === '' ? null : Number(要素.value);
      else データ[項目.名前] = 要素.value.trim();
      if (項目.必須 && (データ[項目.名前] === '' || データ[項目.名前] === null)) {
        通知(`${項目.ラベル}を入力してください`, 'エラー');
        要素.focus();
        return;
      }
    }
    ボタン.disabled = true;
    try { await 送信(データ, 入力); } catch (エラー) { エラー通知(エラー); } finally { ボタン.disabled = false; }
  });
  フォーム要素.入力 = 入力;
  return フォーム要素;
}

// ---------- 表示用の整形 ----------

const 曜日 = ['日', '月', '火', '水', '木', '金', '土'];

export function 今日の日付() {
  const d = new Date();
  return 日付文字列(d);
}

export function 日付文字列(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function 日付を読む(文字列) {
  const [y, m, d] = 文字列.split('-').map(Number);
  return new Date(y, m - 1, d);
}

export function 日付表示(文字列, 年も = false) {
  if (!文字列) return '';
  const d = 日付を読む(文字列.slice(0, 10));
  return `${年も ? `${d.getFullYear()}年` : ''}${d.getMonth() + 1}/${d.getDate()}（${曜日[d.getDay()]}）`;
}

export function 日時表示(文字列) {
  if (!文字列) return '';
  const d = new Date(文字列);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

export function 残り日数(文字列) {
  if (!文字列) return null;
  return Math.round((日付を読む(文字列) - 日付を読む(今日の日付())) / 86400000);
}

export function 率(値) {
  return 値 === null || 値 === undefined ? '—' : `${値}%`;
}

export function 顔写真(メンバー, 大きさ = 40) {
  const 共通 = { class: '顔', style: { width: `${大きさ}px`, height: `${大きさ}px`, fontSize: `${大きさ * 0.42}px` } };
  if (メンバー?.photo) return h('img', { ...共通, src: メンバー.photo, alt: '' });
  return h('span', { ...共通, 'aria-hidden': 'true' }, (メンバー?.name || '?').slice(0, 1));
}

export function バッジ(文言, 種類 = '') {
  return h('span', { class: `バッジ ${種類}` }, 文言);
}

export const 出欠の色 = { 出席: '良', 遅刻: '注意', 早退: '注意', 欠席: '悪' };

// 画像ファイルを正方形に切り抜いて縮小し、data URL にする（顔写真用）
export function 画像を縮小(ファイル, 大きさ = 256) {
  return new Promise((解決, 失敗) => {
    const 読込 = new FileReader();
    読込.onerror = () => 失敗(new Error('画像を読み込めませんでした'));
    読込.onload = () => {
      const 画像 = new Image();
      画像.onerror = () => 失敗(new Error('画像を読み込めませんでした'));
      画像.onload = () => {
        const 辺 = Math.min(画像.width, 画像.height);
        const キャンバス = document.createElement('canvas');
        キャンバス.width = キャンバス.height = 大きさ;
        キャンバス.getContext('2d').drawImage(画像, (画像.width - 辺) / 2, (画像.height - 辺) / 2, 辺, 辺, 0, 0, 大きさ, 大きさ);
        解決(キャンバス.toDataURL('image/jpeg', 0.82));
      };
      画像.src = 読込.result;
    };
    読込.readAsDataURL(ファイル);
  });
}

export function タブ(候補, 現在, 選択時) {
  return h('div', { class: 'タブ', role: 'tablist' },
    候補.map(([値, 表示]) => h('button', {
      class: `タブ項目 ${値 === 現在 ? '選択中' : ''}`, role: 'tab', 'aria-selected': String(値 === 現在),
      onclick: () => 選択時(値),
    }, 表示)));
}
