// 目標管理：チーム目標・個人目標（達成度・期限・振り返り）

import { api, h, 描画, 見出し, コーチか, 状態, バッジ, 空表示, 通知, エラー通知, 確認, シート, フォーム, タブ, 日付表示, 残り日数 } from './共通.js';
import { 進捗バー } from './図表.js';

const 状態の色 = { 進行中: '薄', 達成: '良', 未達成: '悪' };
let 表示 = '進行中';

async function 目標を編集(目標 = null, 選手一覧 = []) {
  const 項目 = [];
  if (!目標) {
    項目.push({ 名前: 'scope', ラベル: '対象', 種類: 'select', 選択肢: コーチか() ? ['チーム', '個人'] : ['個人'] });
    if (コーチか()) 項目.push({ 名前: 'user_id', ラベル: '個人目標の選手（対象が個人のとき）', 種類: 'select', 選択肢: 選手一覧.map((m) => [m.id, m.name]) });
  }
  項目.push(
    { 名前: 'content', ラベル: '目標', 必須: true, 種類: 'textarea', 行数: 2, 例: '例：フリースロー成功率70%' },
    { 名前: 'deadline', ラベル: '期限', 種類: 'date' },
    { 名前: 'progress', ラベル: '達成度（%）', 種類: 'range', 最小: 0, 最大値: 100, 刻み: 5 },
  );
  if (目標) {
    項目.push(
      { 名前: 'status', ラベル: '状態', 種類: 'select', 選択肢: ['進行中', '達成', '未達成'] },
      { 名前: 'reflection', ラベル: '振り返り（できたこと・次に活かすこと）', 種類: 'textarea', 行数: 4 },
    );
  }
  const 保存 = await シート(目標 ? '目標を編集' : '目標を追加', (閉じる) => {
    const f = フォーム(項目, async (v) => {
      if (目標) await api('PUT', `/api/goals/${目標.id}`, v);
      else await api('POST', '/api/goals', { ...v, user_id: v.user_id ? Number(v.user_id) : undefined });
      閉じる(true);
    }, { 値: 目標 || { progress: 0, scope: コーチか() ? 'チーム' : '個人' } });
    // 達成度のスライダーに数値を添える
    const 範囲 = f.入力.progress;
    const 数値 = h('strong', {}, `${範囲.value}%`);
    範囲.addEventListener('input', () => { 数値.textContent = `${範囲.value}%`; });
    範囲.after(数値);
    return [
      f,
      目標 ? h('button', {
        class: 'ボタン 危険 大',
        onclick: async () => {
          if (!(await 確認('この目標を削除しますか？', '削除', true))) return;
          try { await api('DELETE', `/api/goals/${目標.id}`); 閉じる(true); } catch (エラー) { エラー通知(エラー); }
        },
      }, '削除') : null,
    ];
  });
  if (保存) { 通知('保存しました'); 目標画面(); }
}

function 目標カード(g, 選手一覧) {
  const 残り = 残り日数(g.deadline);
  const 編集できる = コーチか() || (g.scope === '個人' && g.user_id === 状態.ユーザー.id);
  return h(編集できる ? 'button' : 'div', { class: 'カード 目標カード', onclick: 編集できる ? () => 目標を編集(g, 選手一覧) : null },
    h('div', { class: '行 間' },
      h('small', {}, g.scope === 'チーム' ? '👥 チーム目標' : `👤 ${g.user_name || ''}`),
      h('div', { class: 'バッジ列' },
        g.status === '進行中' && 残り !== null ? バッジ(残り >= 0 ? `あと${残り}日` : '期限切れ', 残り < 7 ? '注意' : '薄') : null,
        バッジ(g.status, 状態の色[g.status]))),
    h('strong', { class: '目標文' }, g.content),
    h('div', { class: '行 間' }, 進捗バー(g.progress, 100, g.status === '達成' ? 'var(--良)' : null), h('small', {}, `${g.progress}%`)),
    g.deadline ? h('small', {}, `期限：${日付表示(g.deadline, true)}`) : null,
    g.reflection ? h('p', { class: '返信' }, `📝 ${g.reflection}`) : null);
}

export async function 目標画面() {
  const [目標, メンバー] = await Promise.all([api('GET', '/api/goals'), コーチか() ? api('GET', '/api/members') : []]);
  const 選手一覧 = メンバー.filter((m) => m.role === 'player');
  const 対象 = 目標.filter((g) => (表示 === '進行中' ? g.status === '進行中' : g.status !== '進行中'));
  const チーム = 対象.filter((g) => g.scope === 'チーム');
  const 個人 = 対象.filter((g) => g.scope === '個人');
  描画(
    見出し('目標管理', h('button', { class: 'ボタン 小', onclick: () => 目標を編集(null, 選手一覧) }, '＋ 追加'), '#/more'),
    タブ([['進行中', '進行中'], ['終了', '達成・終了（振り返り）']], 表示, (v) => { 表示 = v; 目標画面(); }),
    h('h2', { class: '節見出し' }, '👥 チーム目標'),
    チーム.length ? チーム.map((g) => 目標カード(g, 選手一覧)) : 空表示('チーム目標はありません'),
    h('h2', { class: '節見出し' }, コーチか() ? '👤 選手の個人目標' : '👤 わたしの目標'),
    個人.length ? 個人.map((g) => 目標カード(g, 選手一覧)) : 空表示('個人目標はありません'),
    表示 === '進行中' ? h('p', { class: '補足' }, '期限が来たら「状態」を達成／未達成にして、振り返りを書きましょう') : null);
}
