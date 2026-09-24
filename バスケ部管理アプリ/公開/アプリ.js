// 画面の切り替え（#/〜 のハッシュで遷移）・下部メニュー・ログイン／チーム作成

import {
  api, 置き換え, h, 状態, 描画, 遷移 as 遷移状態, 遷移により中断, 見出し, 読み込み中, エラー表示, フォーム, 通知, ログイン状態を保存, コーチか, シート,
} from './共通.js';

const ルート表 = [
  ['/home', (p, 確) => import('./画面_ホーム.js').then(確).then((m) => m.ホーム画面())],
  ['/schedule', (p, 確) => import('./画面_予定.js').then(確).then((m) => m.予定画面())],
  ['/events/new', (p, 確) => import('./画面_予定.js').then(確).then((m) => m.予定編集画面(null))],
  ['/events/:id/edit', (p, 確) => import('./画面_予定.js').then(確).then((m) => m.予定編集画面(p.id))],
  ['/events/:id', (p, 確) => import('./画面_予定.js').then(確).then((m) => m.予定詳細画面(p.id))],
  ['/history', (p, 確) => import('./画面_予定.js').then(確).then((m) => m.練習履歴画面())],
  ['/menus', (p, 確) => import('./画面_練習メニュー.js').then(確).then((m) => m.練習メニュー画面())],
  ['/tactics', (p, 確) => import('./画面_作戦ボード.js').then(確).then((m) => m.戦術一覧画面())],
  ['/tactics/new', (p, 確) => import('./画面_作戦ボード.js').then(確).then((m) => m.戦術編集画面(null))],
  ['/tactics/:id/edit', (p, 確) => import('./画面_作戦ボード.js').then(確).then((m) => m.戦術編集画面(p.id))],
  ['/tactics/:id', (p, 確) => import('./画面_作戦ボード.js').then(確).then((m) => m.戦術詳細画面(p.id))],
  ['/members', (p, 確) => import('./画面_メンバー.js').then(確).then((m) => m.メンバー一覧画面())],
  ['/members/:id', (p, 確) => import('./画面_メンバー.js').then(確).then((m) => m.メンバー詳細画面(p.id))],
  ['/players', (p, 確) => import('./画面_選手カルテ.js').then(確).then((m) => m.選手一覧画面())],
  ['/karte/:id', (p, 確) => import('./画面_選手カルテ.js').then(確).then((m) => m.選手カルテ画面(p.id))],
  ['/karte', (p, 確) => import('./画面_選手カルテ.js').then(確).then((m) => m.選手カルテ画面(状態.ユーザー.id))],
  ['/stats/entry', (p, 確) => import('./画面_選手カルテ.js').then(確).then((m) => m.スタッツ入力画面())],
  ['/stats/team', (p, 確) => import('./画面_選手カルテ.js').then(確).then((m) => m.チームスタッツ画面())],
  ['/skills/:id', (p, 確) => import('./画面_スキル.js').then(確).then((m) => m.スキル画面(p.id))],
  ['/skills', (p, 確) => import('./画面_スキル.js').then(確).then((m) => m.スキル画面(状態.ユーザー.id))],
  ['/steps-overview', (p, 確) => import('./画面_スキル.js').then(確).then((m) => m.ステップ一覧表画面())],
  ['/drills', (p, 確) => import('./画面_スキル.js').then(確).then((m) => m.ドリル管理画面())],
  ['/goals', (p, 確) => import('./画面_目標.js').then(確).then((m) => m.目標画面())],
  ['/board', (p, 確) => import('./画面_掲示板.js').then(確).then((m) => m.掲示板画面())],
  ['/board/:id', (p, 確) => import('./画面_掲示板.js').then(確).then((m) => m.投稿詳細画面(p.id))],
  ['/more', () => その他画面()],
  ['/settings', (p, 確) => import('./画面_設定.js').then(確).then((m) => m.設定画面())],
];

function ルートを探す(パス) {
  for (const [型, 処理] of ルート表) {
    const 名前 = [];
    const 正規 = new RegExp(`^${型.replace(/:(\w+)/g, (_, n) => { 名前.push(n); return '(\\d+)'; })}$`);
    const 一致 = パス.match(正規);
    if (一致) return [処理, Object.fromEntries(名前.map((n, i) => [n, Number(一致[i + 1])]))];
  }
  return null;
}

const 下部メニュー = () => [
  ['#/home', '🏠', 'ホーム'],
  ['#/schedule', '📅', '予定'],
  ['#/tactics', '📋', '作戦'],
  コーチか() ? ['#/players', '👥', '選手'] : ['#/karte', '📈', 'カルテ'],
  ['#/more', '☰', 'その他'],
];

function メニューを描画(パス) {
  const nav = document.getElementById('下部メニュー');
  if (!状態.トークン) { nav.hidden = true; return; }
  nav.hidden = false;
  置き換え(nav, ...下部メニュー().map(([リンク, 絵, 名前]) => {
    const 選択 = パス.startsWith(リンク.slice(1)) || (リンク === '#/players' && /^\/(karte|skills|stats|steps)/.test(パス))
      || (リンク === '#/karte' && /^\/(karte|skills)/.test(パス));
    return h('a', { href: リンク, class: 選択 ? '選択中' : '', 'aria-current': 選択 ? 'page' : null },
      h('span', { class: '絵', 'aria-hidden': 'true' }, 絵), h('span', {}, 名前));
  }));
}

async function 遷移() {
  遷移状態.番号 += 1;
  const パス = (location.hash.replace(/^#/, '') || '/home').split('?')[0];
  if (!状態.トークン) {
    メニューを描画(パス);
    return パス === '/register' ? チーム作成画面() : ログイン画面();
  }
  if (パス === '/login' || パス === '/register') { location.hash = '#/home'; return; }
  メニューを描画(パス);
  const 見つけた = ルートを探す(パス);
  if (!見つけた) { location.hash = '#/home'; return; }
  読み込み中();
  try {
    const 番号 = 遷移状態.番号;
    // 画面の部品を読み込んでいる間に別の画面へ移ったら、古い画面は描かない
    const 確 = (m) => { if (番号 !== 遷移状態.番号) throw new 遷移により中断(); return m; };
    await 見つけた[0](見つけた[1], 確);
  } catch (エラー) {
    if (エラー instanceof 遷移により中断) return;
    if (エラー.ステータス !== 401) エラー表示(エラー);
  }
}

// ---------- ログイン・チーム作成 ----------

function ホームへ() {
  // すでに #/home のときは hashchange が起きないので直接描画する
  if (location.hash === '#/home') 遷移(); else location.hash = '#/home';
}

function ログイン画面() {
  const 前回のコード = (() => { try { return localStorage.getItem('last_team_code') || ''; } catch { return ''; } })();
  描画(
    h('div', { class: 'ログイン' },
      h('div', { class: 'ロゴ', 'aria-hidden': 'true' }, '🏀'),
      h('h1', {}, 'バスケ部ノート'),
      h('p', { class: '説明' }, 'チーム運営・練習メニュー・作戦・選手の成長をひとつに'),
      h('div', { class: 'カード' },
        フォーム([
          { 名前: 'team_code', ラベル: 'チームコード', 必須: true, 例: '例：AB23CD', 既定: 前回のコード, 自動補完: 'organization' },
          { 名前: 'login_id', ラベル: 'ログインID', 必須: true, 自動補完: 'username', 入力モード: 'email' },
          { 名前: 'password', ラベル: 'パスワード', 種類: 'password', 必須: true, 自動補完: 'current-password' },
        ], async (値) => {
          const 結果 = await api('POST', '/api/login', 値);
          try { localStorage.setItem('last_team_code', 値.team_code.toUpperCase()); } catch { /* 無視 */ }
          ログイン状態を保存(結果.token, 結果.user, 結果.team);
          ホームへ();
        }, { 送信文言: 'ログイン' })),
      h('p', { class: '補足' }, 'チームコードとログインIDはコーチ（顧問）から教えてもらってください'),
      h('a', { class: 'ボタン 控えめ 大', href: '#/register' }, '新しくチームを作る（コーチ用）')));
}

function チーム作成画面() {
  描画(
    見出し('チームを作る', null, '#/login'),
    h('div', { class: 'カード' },
      h('p', {}, 'コーチ（顧問）がチームを作成します。作成後に表示される「チームコード」を選手に伝えてください。'),
      フォーム([
        { 名前: 'team_name', ラベル: 'チーム名', 必須: true, 例: '例：〇〇高校 男子バスケ部' },
        { 名前: 'name', ラベル: 'あなたの氏名', 必須: true },
        { 名前: 'login_id', ラベル: 'ログインID（半角英数字）', 必須: true, 補足: '3〜30文字。ログインのときに使います', 自動補完: 'username' },
        { 名前: 'password', ラベル: 'パスワード（8文字以上）', 種類: 'password', 必須: true, 自動補完: 'new-password' },
      ], async (値) => {
        const 結果 = await api('POST', '/api/teams', 値);
        try { localStorage.setItem('last_team_code', 結果.team.code); } catch { /* 無視 */ }
        ログイン状態を保存(結果.token, 結果.user, 結果.team);
        await シート('チームを作成しました', (閉じる) => [
          h('p', {}, '選手がログインするときに使うチームコードです。'),
          h('p', { class: 'チームコード' }, 結果.team.code),
          h('p', { class: '補足' }, '「その他 → 設定」からいつでも確認できます。次に「メンバー」から選手を登録しましょう。'),
          h('button', { class: 'ボタン 大', onclick: () => 閉じる() }, 'はじめる'),
        ]);
        ホームへ();
      }, { 送信文言: 'チームを作成' })));
}

// ---------- その他 ----------

function その他画面() {
  const 項目 = [
    ['#/board', '📣', '連絡・掲示板', 'お知らせと既読チェック'],
    ['#/members', '👤', 'メンバー', 'プロフィール・背番号・顔写真'],
    ['#/goals', '🎯', '目標管理', '個人目標とチーム目標'],
    ['#/menus', '🏋️', '練習メニュー', 'ドリルのテンプレート'],
    ['#/history', '🗂️', '練習履歴', '過去の練習を検索'],
    ['#/stats/team', '📊', 'チームスタッツ', '選手別の平均・成功率'],
  ];
  if (コーチか()) {
    項目.push(
      ['#/stats/entry', '✍️', 'スタッツ入力', '試合ごとにまとめて入力'],
      ['#/steps-overview', '🪜', 'ステップ進行一覧', '全選手のステップ状況'],
      ['#/drills', '🧩', 'ステップドリル管理', 'スキル×レベルごとのドリル'],
    );
  } else {
    項目.push(['#/skills', '🧭', 'スキル診断', '能力値と次の練習']);
  }
  項目.push(['#/settings', '⚙️', '設定', 'パスワード・チーム情報・ログアウト']);
  描画(
    見出し('その他'),
    h('nav', { class: 'リスト' }, 項目.map(([リンク, 絵, 名前, 説明]) => h('a', { class: 'リスト項目', href: リンク },
      h('span', { class: '絵 大', 'aria-hidden': 'true' }, 絵),
      h('div', { class: '伸びる' }, h('strong', {}, 名前), h('small', {}, 説明)),
      h('span', { class: '矢印', 'aria-hidden': 'true' }, '›')))));
}

// ---------- 起動 ----------

window.addEventListener('hashchange', 遷移);
window.addEventListener('online', () => 通知('オンラインに戻りました'));
window.addEventListener('offline', () => 通知('オフラインです。保存済みの練習メニュー・作戦は閲覧できます', '注意'));
遷移();

if ('serviceWorker' in navigator && location.protocol !== 'file:') {
  navigator.serviceWorker.register('./オフライン対応.js').catch(() => { /* 対応していない環境では無視 */ });
}
