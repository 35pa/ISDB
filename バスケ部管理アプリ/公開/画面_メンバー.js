// メンバー一覧・個人プロフィール（顔写真・学年・ポジション・背番号の編集はコーチのみ）

import { api, 置き換え, h, 描画, 見出し, コーチか, 状態, 顔写真, バッジ, 空表示, 通知, エラー通知, 確認, シート, フォーム, 画像を縮小 } from './共通.js';

const ポジション = ['', 'PG', 'SG', 'SF', 'PF', 'C'];
const 学年 = ['', '1年', '2年', '3年'];

function 写真選択(初期) {
  let 値 = 初期 || '';
  const 表示 = h('div', { class: '写真プレビュー' });
  const 更新 = () => 置き換え(表示, 顔写真({ photo: 値, name: '？' }, 88));
  更新();
  const 入力 = h('input', { type: 'file', accept: 'image/*', class: '隠す', id: '写真入力' });
  入力.addEventListener('change', async () => {
    const ファイル = 入力.files?.[0];
    if (!ファイル) return;
    try { 値 = await 画像を縮小(ファイル); 更新(); } catch (エラー) { エラー通知(エラー); }
  });
  return {
    要素: h('div', { class: '写真選択' }, 表示,
      h('div', { class: 'ボタン列' },
        h('label', { class: 'ボタン 控えめ 小', for: '写真入力' }, '📷 写真を選ぶ'),
        h('button', { type: 'button', class: 'ボタン 控えめ 小', onclick: () => { 値 = ''; 更新(); } }, '削除')),
      入力),
    値: () => 値,
  };
}

function ログイン情報を表示(メンバー, パスワード) {
  return シート('ログイン情報', (閉じる) => [
    h('p', {}, `${メンバー.name} さんに次の情報を伝えてください。初回ログイン後に「設定」からパスワードを変更できます。`),
    h('dl', { class: 'ログイン情報' },
      h('dt', {}, 'チームコード'), h('dd', {}, 状態.チーム.code),
      h('dt', {}, 'ログインID'), h('dd', {}, メンバー.login_id),
      h('dt', {}, 'パスワード'), h('dd', {}, パスワード)),
    h('p', { class: '補足' }, 'この画面を閉じるとパスワードは再表示できません（再発行は可能です）'),
    h('button', { class: 'ボタン 大', onclick: () => 閉じる() }, '伝えました'),
  ]);
}

async function メンバー編集(メンバー = null) {
  const 写真 = 写真選択(メンバー?.photo);
  const 結果 = await シート(メンバー ? 'プロフィールを編集' : 'メンバーを追加', (閉じる) => {
    const 項目 = [
      { 名前: 'name', ラベル: '氏名', 必須: true },
      ...(メンバー ? [] : [{ 名前: 'login_id', ラベル: 'ログインID（半角英数字）', 必須: true, 補足: '例：sato4。ログインに使います', 入力モード: 'email' }]),
      { 名前: 'role', ラベル: '役割', 種類: 'select', 選択肢: [['player', '選手'], ['coach', 'コーチ・顧問']] },
      { 名前: 'grade', ラベル: '学年', 種類: 'select', 選択肢: 学年.map((g) => [g, g || '未設定']) },
      { 名前: 'position', ラベル: 'ポジション', 種類: 'select', 選択肢: ポジション.map((p) => [p, p || '未設定']) },
      { 名前: 'number', ラベル: '背番号', 入力モード: 'numeric', 最大: 3 },
    ];
    const f = フォーム(項目, async (値) => {
      const 本文 = { ...値, photo: 写真.値() };
      if (メンバー) {
        await api('PUT', `/api/members/${メンバー.id}`, 本文);
        閉じる({ 保存: true });
      } else {
        const r = await api('POST', '/api/members', 本文);
        閉じる({ 保存: true, 新規: r });
      }
    }, { 値: メンバー || { role: 'player' } });
    f.prepend(写真.要素);
    return f;
  });
  if (!結果?.保存) return false;
  通知('保存しました');
  if (結果.新規) await ログイン情報を表示(結果.新規.member, 結果.新規.initial_password);
  return true;
}

export async function メンバー一覧画面() {
  const メンバー = await api('GET', '/api/members');
  const コーチ = メンバー.filter((m) => m.role === 'coach');
  const 選手 = メンバー.filter((m) => m.role === 'player');
  const 学年別 = {};
  for (const m of 選手) (学年別[m.grade || '学年未設定'] ||= []).push(m);
  const 行 = (m) => h('a', { class: 'リスト項目', href: `#/members/${m.id}` },
    顔写真(m, 44),
    h('div', { class: '伸びる' },
      h('strong', {}, m.name),
      h('small', {}, [m.position, m.grade].filter(Boolean).join(' ・ '))),
    m.number ? h('span', { class: '背番号' }, m.number) : null);
  描画(
    見出し(`メンバー（${メンバー.length}人）`, コーチか() ? h('button', { class: 'ボタン 小', onclick: async () => { if (await メンバー編集()) メンバー一覧画面(); } }, '＋ 追加') : null, '#/more'),
    h('section', { class: 'カード' }, h('h2', {}, 'コーチ・顧問'), h('div', { class: 'リスト' }, コーチ.map(行))),
    選手.length ? Object.entries(学年別).sort(([a], [b]) => b.localeCompare(a, 'ja')).map(([g, 件]) => h('section', { class: 'カード' },
      h('h2', {}, `${g}（${件.length}人）`), h('div', { class: 'リスト' }, 件.map(行))))
      : h('div', { class: 'カード' }, 空表示('まだ選手がいません'), コーチか() ? h('p', { class: '補足 中央' }, '右上の「＋ 追加」から選手を登録してください') : null));
}

export async function メンバー詳細画面(id) {
  const m = await api('GET', `/api/members/${id}`);
  const コーチ = コーチか();
  const 本人 = 状態.ユーザー.id === m.id;
  const 見られる = m.role === 'player' && (コーチ || 本人);
  描画(
    見出し('プロフィール', null, '#/members'),
    h('section', { class: 'カード プロフィール' },
      顔写真(m, 112),
      h('h2', {}, m.name),
      h('div', { class: 'バッジ列 中央' },
        m.number ? バッジ(`#${m.number}`, '強調') : null,
        m.position ? バッジ(m.position, '味方') : null,
        m.grade ? バッジ(m.grade, '薄') : null,
        m.role === 'coach' ? バッジ('コーチ', '薄') : null),
      コーチ ? h('small', {}, `ログインID：${m.login_id}`) : null),
    見られる ? h('nav', { class: 'リスト カード' },
      h('a', { class: 'リスト項目', href: `#/karte/${m.id}` }, h('span', { class: '絵 大' }, '📈'), h('strong', { class: '伸びる' }, '選手カルテ'), h('span', { class: '矢印' }, '›')),
      h('a', { class: 'リスト項目', href: `#/skills/${m.id}` }, h('span', { class: '絵 大' }, '🧭'), h('strong', { class: '伸びる' }, 'スキル診断・ステップ練習'), h('span', { class: '矢印' }, '›'))) : null,
    コーチ ? h('div', { class: 'ボタン列 折返し' },
      h('button', { class: 'ボタン', onclick: async () => { if (await メンバー編集(m)) メンバー詳細画面(id); } }, '編集'),
      h('button', {
        class: 'ボタン 控えめ',
        onclick: async () => {
          if (!(await 確認(`${m.name} さんのパスワードを再発行しますか？今のパスワードは使えなくなります。`, '再発行'))) return;
          try { const r = await api('POST', `/api/members/${id}/reset-password`); await ログイン情報を表示(m, r.initial_password); } catch (エラー) { エラー通知(エラー); }
        },
      }, 'パスワード再発行'),
      本人 ? null : h('button', {
        class: 'ボタン 危険',
        onclick: async () => {
          if (!(await 確認(`${m.name} さんを退部（一覧から外す）にしますか？スタッツなどの記録は残ります。`, '退部にする', true))) return;
          try { await api('DELETE', `/api/members/${id}`); 通知('退部にしました'); location.hash = '#/members'; } catch (エラー) { エラー通知(エラー); }
        },
      }, '退部にする')) : h('p', { class: '補足' }, 'プロフィール（顔写真・学年・背番号など）の変更はコーチに依頼してください'));
}
