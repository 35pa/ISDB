// 設定：チーム情報（チームコード）・パスワード変更・ログアウト

import { api, h, 描画, 見出し, コーチか, 通知, 確認, シート, フォーム, ログイン状態を保存, ログイン状態を消去 } from './共通.js';
import { 標準データを追加 } from './画面_スキル.js';

export async function 設定画面() {
  const 自分 = await api('GET', '/api/me');
  ログイン状態を保存(null, 自分.user, 自分.team);
  描画(
    見出し('設定', null, '#/more'),
    h('section', { class: 'カード' },
      h('h2', {}, 'チーム'),
      h('p', {}, h('strong', {}, 自分.team.name)),
      h('p', {}, 'チームコード'),
      h('p', { class: 'チームコード' }, 自分.team.code),
      h('small', {}, '選手がログインするときに入力します。チーム外の人には教えないでください。'),
      コーチか() ? h('button', {
        class: 'ボタン 控えめ',
        onclick: async () => {
          const 名前 = await シート('チーム名を変更', (閉じる) => フォーム([{ 名前: 'name', ラベル: 'チーム名', 必須: true }], async (v) => {
            await api('PUT', '/api/team', v);
            閉じる(v.name);
          }, { 値: { name: 自分.team.name } }));
          if (名前) { 通知('変更しました'); 設定画面(); }
        },
      }, 'チーム名を変更') : null,
      コーチか() ? h('button', { class: 'ボタン 控えめ', onclick: () => 標準データを追加() }, '📥 標準のドリル・作戦テンプレートを追加') : null),
    h('section', { class: 'カード' },
      h('h2', {}, 'アカウント'),
      h('p', {}, `${自分.user.name}（ログインID：${自分.user.login_id}）`),
      h('h3', { class: 'フォーム小見出し' }, 'パスワード変更'),
      フォーム([
        { 名前: 'current', ラベル: '今のパスワード', 種類: 'password', 必須: true, 自動補完: 'current-password' },
        { 名前: 'new', ラベル: '新しいパスワード（8文字以上）', 種類: 'password', 必須: true, 自動補完: 'new-password' },
      ], async (v, 入力) => {
        const r = await api('PUT', '/api/me/password', v);
        ログイン状態を保存(r.token);
        入力.current.value = '';
        入力.new.value = '';
        通知('パスワードを変更しました（他の端末はログアウトされます）');
      }, { 送信文言: '変更する' })),
    h('button', {
      class: 'ボタン 危険 大',
      onclick: async () => {
        if (!(await 確認('ログアウトしますか？', 'ログアウト'))) return;
        try { await api('POST', '/api/logout'); } catch { /* オフラインでもログアウトはする */ }
        ログイン状態を消去();
        location.hash = '#/login';
      },
    }, 'ログアウト'),
    h('p', { class: '補足 中央' }, 'バスケ部ノート ・ ホーム画面に追加するとアプリのように使えます'));
}
