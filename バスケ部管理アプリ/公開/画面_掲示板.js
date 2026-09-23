// 連絡・掲示板：お知らせ配信（コーチ）と既読チェック、チーム内の掲示板・コメント

import { api, h, 描画, 見出し, コーチか, 状態, バッジ, 空表示, 通知, エラー通知, 確認, シート, フォーム, タブ, 日時表示, オフライン注記 } from './共通.js';
import { 進捗バー } from './図表.js';

let 表示 = 'お知らせ';

async function 投稿する() {
  const 保存 = await シート('投稿する', (閉じる) => フォーム([
    { 名前: 'kind', ラベル: '種類', 種類: 'select', 選択肢: コーチか() ? [['お知らせ', 'お知らせ（既読チェックあり）'], ['掲示板', '掲示板']] : [['掲示板', '掲示板']] },
    { 名前: 'title', ラベル: 'タイトル', 必須: true },
    { 名前: 'body', ラベル: '本文', 種類: 'textarea', 行数: 6 },
  ], async (v) => { const r = await api('POST', '/api/posts', v); 閉じる(r.id); }, { 送信文言: '投稿', 値: { kind: 表示 === 'お知らせ' && コーチか() ? 'お知らせ' : '掲示板' } }));
  if (保存) { 通知('投稿しました'); location.hash = `#/board/${保存}`; }
}

export async function 掲示板画面() {
  const 投稿 = await api('GET', `/api/posts?kind=${encodeURIComponent(表示)}`);
  描画(
    見出し('連絡・掲示板', h('button', { class: 'ボタン 小', onclick: 投稿する }, '＋ 投稿'), '#/more'),
    オフライン注記(投稿),
    タブ([['お知らせ', '📣 お知らせ'], ['掲示板', '💬 掲示板']], 表示, (v) => { 表示 = v; 掲示板画面(); }),
    投稿.length ? h('div', { class: 'リスト カード' }, 投稿.map((p) => h('a', { class: 'リスト項目', href: `#/board/${p.id}` },
      p.is_read ? null : h('span', { class: '未読点', 'aria-label': '未読' }),
      h('div', { class: '伸びる' },
        h('strong', {}, p.title),
        h('small', {}, `${p.author_name || ''} ・ ${日時表示(p.created_at)}${p.comment_count ? ` ・ 💬${p.comment_count}` : ''}`),
        p.kind === 'お知らせ' && コーチか() ? h('div', { class: '行' }, 進捗バー(p.read_count, p.member_count), h('small', {}, `既読 ${p.read_count}/${p.member_count}`)) : null),
      h('span', { class: '矢印' }, '›')))) : 空表示(表示 === 'お知らせ' ? 'お知らせはありません' : 'まだ投稿がありません'));
}

export async function 投稿詳細画面(id) {
  const p = await api('GET', `/api/posts/${id}`);
  const 自分 = 状態.ユーザー.id;
  const コメント欄 = h('textarea', { rows: 2, maxLength: 1000, placeholder: 'コメントを書く', 'aria-label': 'コメント' });
  const 未読 = (p.reads || []).filter((r) => !r.read_at);
  描画(
    見出し(p.kind, null, '#/board'),
    h('article', { class: 'カード' },
      h('h2', {}, p.title),
      h('small', {}, `${p.author_name || ''} ・ ${日時表示(p.created_at)}`),
      h('p', { class: '本文' }, p.body),
      p.kind === 'お知らせ' ? h('div', { class: '行 間' }, 進捗バー(p.read_count, p.member_count), h('small', {}, `既読 ${p.read_count}/${p.member_count}`)) : null),

    コーチか() && p.kind === 'お知らせ' ? h('details', { class: 'カード', open: 未読.length > 0 },
      h('summary', {}, `既読状況（未読 ${未読.length}人）`),
      h('div', { class: 'リスト' }, p.reads.map((r) => h('div', { class: 'リスト項目' },
        h('span', { class: '伸びる' }, r.name, r.role === 'coach' ? バッジ('コーチ', '薄') : null),
        r.read_at ? h('small', { class: '既読' }, `既読 ${日時表示(r.read_at)}`) : バッジ('未読', '注意'))))) : null,

    h('section', { class: 'カード' },
      h('h2', {}, `コメント（${p.comments.length}）`),
      p.comments.length ? h('div', { class: 'リスト' }, p.comments.map((c) => h('div', { class: 'リスト項目 縦' },
        h('div', { class: '行 間' }, h('small', {}, `${c.user_name || '退部メンバー'} ・ ${日時表示(c.created_at)}`),
          c.user_id === 自分 || コーチか() ? h('button', {
            class: '小リンク',
            onclick: async () => { if (await 確認('コメントを削除しますか？', '削除', true)) { await api('DELETE', `/api/comments/${c.id}`).catch(エラー通知); 投稿詳細画面(id); } },
          }, '削除') : null),
        h('p', {}, c.body)))) : null,
      コメント欄,
      h('button', {
        class: 'ボタン',
        onclick: async () => {
          if (!コメント欄.value.trim()) return;
          try { await api('POST', `/api/posts/${id}/comments`, { body: コメント欄.value }); 投稿詳細画面(id); } catch (エラー) { エラー通知(エラー); }
        },
      }, '送信')),

    p.author_id === 自分 || コーチか() ? h('button', {
      class: 'ボタン 危険',
      onclick: async () => {
        if (!(await 確認('この投稿を削除しますか？', '削除', true))) return;
        try { await api('DELETE', `/api/posts/${id}`); 通知('削除しました'); location.hash = '#/board'; } catch (エラー) { エラー通知(エラー); }
      },
    }, '投稿を削除') : null);
}
