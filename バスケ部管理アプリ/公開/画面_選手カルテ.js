// 選手カルテ：個人課題・スタッツ推移・シュートチャート・成長記録カレンダー・フィードバック
// スタッツ入力（試合ごとにまとめて）・チームスタッツ

import {
  api, 置き換え, h, 描画, 見出し, コーチか, 状態, 顔写真, バッジ, 空表示, 通知, エラー通知, 確認, シート, フォーム, タブ,
  日付表示, 日時表示, 今日の日付, 率, オフライン注記,
} from './共通.js';
import { シュートチャート, 折れ線グラフ, 月カレンダー, 進捗バー, エリア位置 } from './図表.js';

const カルテのタブ = [['概要', '概要'], ['スタッツ', 'スタッツ'], ['成長記録', '成長記録'], ['フィードバック', 'コメント']];
let 選択タブ = '概要';
let 表示月 = 今日の日付().slice(0, 7);

// ---------- 選手一覧（コーチ用） ----------

export async function 選手一覧画面() {
  const [メンバー, 一覧表] = await Promise.all([api('GET', '/api/members'), api('GET', '/api/steps/overview')]);
  const 進捗 = Object.fromEntries(一覧表.players.map((p) => [p.player.id, p]));
  const 選手 = メンバー.filter((m) => m.role === 'player');
  描画(
    見出し('選手'),
    h('div', { class: 'ボタン列 折返し' },
      h('a', { class: 'ボタン 小', href: '#/stats/entry' }, '✍️ スタッツ入力'),
      h('a', { class: 'ボタン 控えめ 小', href: '#/steps-overview' }, '🪜 ステップ進行一覧'),
      h('a', { class: 'ボタン 控えめ 小', href: '#/stats/team' }, '📊 チームスタッツ')),
    選手.length ? h('div', { class: 'リスト カード' }, 選手.map((m) => {
      const p = 進捗[m.id];
      const 完了 = p ? p.categories.reduce((a, c) => a + c.completed, 0) : 0;
      const 全体 = p ? p.categories.reduce((a, c) => a + c.total, 0) : 0;
      const 優先 = p ? p.categories.filter((c) => c.priority).sort((a, b) => a.priority - b.priority).map((c) => c.category_name) : [];
      return h('div', { class: 'リスト項目' },
        顔写真(m, 44),
        h('a', { class: '伸びる', href: `#/karte/${m.id}` },
          h('strong', {}, m.number ? `#${m.number} ` : '', m.name),
          h('small', {}, [m.position, m.grade, 優先.length ? `伸ばす：${優先.join('・')}` : 'スキル未診断'].filter(Boolean).join(' ・ ')),
          進捗バー(完了, 全体 || 1)),
        h('a', { class: 'ボタン 控えめ 小', href: `#/skills/${m.id}` }, 'スキル'));
    })) : h('div', { class: 'カード' }, 空表示('選手がいません'), h('a', { class: 'ボタン', href: '#/members' }, 'メンバーを登録する')));
}

// ---------- カルテ ----------

export async function 選手カルテ画面(id) {
  const k = await api('GET', `/api/players/${id}/karte`);
  const 本人 = 状態.ユーザー.id === id;
  const 戻る = コーチか() ? '#/players' : null;
  const 中身 = h('div', {});
  const 切替 = (v) => { 選択タブ = v; 描画タブ(); タブ欄.replaceWith(タブ欄 = タブ(カルテのタブ, 選択タブ, 切替)); };
  let タブ欄 = タブ(カルテのタブ, 選択タブ, 切替);
  const 描画タブ = () => {
    置き換え(中身, h('div', { class: '読み込み' }, '読み込み中…'));
    const 処理 = { 概要: 概要タブ, スタッツ: スタッツタブ, 成長記録: 成長記録タブ, フィードバック: フィードバックタブ }[選択タブ];
    Promise.resolve(処理(k, id, 本人, 中身)).catch((エラー) => 置き換え(中身, h('p', { class: 'エラー' }, エラー.message)));
  };
  描画(
    見出し(本人 ? 'マイカルテ' : `${k.player.name} のカルテ`, null, 戻る),
    オフライン注記(k),
    h('div', { class: 'カルテ見出し' },
      顔写真(k.player, 56),
      h('div', { class: '伸びる' },
        h('strong', {}, k.player.name),
        h('small', {}, [k.player.number && `#${k.player.number}`, k.player.position, k.player.grade].filter(Boolean).join(' ・ '))),
      h('a', { class: 'ボタン 控えめ 小', href: 本人 ? '#/skills' : `#/skills/${id}` }, '🧭 スキル')),
    タブ欄,
    中身);
  描画タブ();
}

function 概要タブ(k, id, 本人, 中身) {
  const 課題を編集 = async (課題 = null) => {
    const 保存 = await シート(課題 ? '課題を編集' : '課題を追加', (閉じる) => [
      フォーム([
        { 名前: 'title', ラベル: '課題', 必須: true, 例: '例：左手のレイアップ' },
        { 名前: 'detail', ラベル: '詳細・改善のポイント', 種類: 'textarea' },
        ...(課題 ? [{ 名前: 'status', ラベル: '状態', 種類: 'select', 選択肢: ['取組中', '解決'] }] : []),
      ], async (v) => {
        if (課題) await api('PUT', `/api/issues/${課題.id}`, v); else await api('POST', `/api/players/${id}/issues`, v);
        閉じる(true);
      }, { 値: 課題 || {} }),
      課題 ? h('button', {
        class: 'ボタン 危険 大',
        onclick: async () => { if (await 確認('この課題を削除しますか？', '削除', true)) { await api('DELETE', `/api/issues/${課題.id}`).catch(エラー通知); 閉じる(true); } },
      }, '削除') : null,
    ]);
    if (保存) { 通知('保存しました'); 選手カルテ画面(id); }
  };
  const s = k.stats_summary;
  置き換え(中身, 
    h('section', { class: 'カード' },
      h('div', { class: '行 間' }, h('h2', {}, '🩺 個人の課題'), h('button', { class: 'ボタン 小', onclick: () => 課題を編集() }, '＋ 追加')),
      k.issues.length ? h('div', { class: 'リスト' }, k.issues.map((i) => h('button', { class: 'リスト項目', onclick: () => 課題を編集(i) },
        h('div', { class: '伸びる' }, h('strong', { class: i.status === '解決' ? '打消し' : '' }, i.title), i.detail ? h('small', {}, i.detail) : null),
        バッジ(i.status, i.status === '解決' ? '良' : '注意')))) : 空表示('登録された課題はありません')),
    h('section', { class: 'カード' },
      h('h2', {}, '📊 スタッツ（1試合平均）'),
      s.games ? h('div', { class: '数値タイル' },
        タイル('試合', s.games), タイル('得点', s.averages.points), タイル('リバウンド', s.averages.rebounds), タイル('アシスト', s.averages.assists),
        タイル('FG%', 率(s.fg_pct)), タイル('3P%', 率(s.tp_pct)), タイル('FT%', 率(s.ft_pct)), タイル('スティール', s.averages.steals))
        : 空表示('まだ試合の記録がありません')),
    h('section', { class: 'カード' },
      h('div', { class: '行 間' }, h('h2', {}, '🎯 個人目標'), h('a', { class: '小リンク', href: '#/goals' }, '目標管理')),
      k.goals.length ? h('div', { class: 'リスト' }, k.goals.map((g) => h('div', { class: 'リスト項目 縦' },
        h('div', { class: '行 間' }, h('strong', {}, g.content), バッジ(g.status, g.status === '達成' ? '良' : g.status === '未達成' ? '悪' : '薄')),
        進捗バー(g.progress)))) : 空表示('個人目標はありません')),
    k.feedback.length ? h('section', { class: 'カード' },
      h('h2', {}, '💬 最近のフィードバック'),
      h('div', { class: 'リスト' }, k.feedback.slice(0, 2).map((f) => h('div', { class: 'リスト項目 縦' },
        h('small', {}, `${f.coach_name || 'コーチ'} ・ ${日時表示(f.created_at)}`), h('p', {}, f.body))))) : null);
}

function タイル(名前, 値) {
  return h('div', { class: 'タイル' }, h('strong', {}, 値), h('small', {}, 名前));
}

async function スタッツタブ(k, id, 本人, 中身) {
  const データ = await api('GET', `/api/players/${id}/stats`);
  const s = データ.summary;
  const 推移 = s.trend.slice(-12);
  置き換え(中身, 
    s.games ? h('section', { class: 'カード' },
      h('h2', {}, '📈 推移（直近12試合）'),
      折れ線グラフ(推移.map((t) => t.date.slice(5).replace('-', '/')), [
        { 名前: '得点', 値: 推移.map((t) => t.points), 色: 'var(--系列1)' },
        { 名前: 'リバウンド', 値: 推移.map((t) => t.rebounds), 色: 'var(--系列2)' },
        { 名前: 'アシスト', 値: 推移.map((t) => t.assists), 色: 'var(--系列3)' },
      ]),
      折れ線グラフ(推移.map((t) => t.date.slice(5).replace('-', '/')), [{ 名前: 'FG成功率', 値: 推移.map((t) => t.fg_pct), 色: 'var(--系列4)' }], { 単位: '%' })) : null,
    h('section', { class: 'カード' },
      h('h2', {}, '🏀 シュートチャート（エリア別成功率）'),
      シュートチャート(s.shot_chart),
      h('div', { class: '凡例' },
        h('span', {}, h('i', { style: { background: 'var(--良)' } }), '50%以上'),
        h('span', {}, h('i', { style: { background: 'var(--注意)' } }), '35〜49%'),
        h('span', {}, h('i', { style: { background: 'var(--悪)' } }), '35%未満')),
      h('div', { class: '数値タイル' }, タイル('FG%', 率(s.fg_pct)), タイル('3P%', 率(s.tp_pct)), タイル('FT%', 率(s.ft_pct)))),
    h('section', { class: 'カード' },
      h('div', { class: '行 間' }, h('h2', {}, '📋 試合ごとの記録'), コーチか() ? h('button', { class: 'ボタン 小', onclick: () => 個別スタッツ編集(id, null) }, '＋ 追加') : null),
      データ.rows.length ? h('div', { class: '表の枠' }, h('table', { class: '表' },
        h('thead', {}, h('tr', {}, ['日付', '試合', '得点', 'RB', 'AS', 'ST', 'BK', 'TO', 'FG', '3P', 'FT'].map((c) => h('th', {}, c)))),
        h('tbody', {}, データ.rows.map((r) => h('tr', { class: コーチか() ? '押せる' : '', onclick: コーチか() ? () => 個別スタッツ編集(id, r) : null },
          h('td', {}, r.date.slice(5).replace('-', '/')), h('td', {}, r.label), h('td', {}, h('strong', {}, r.points)),
          h('td', {}, r.rebounds), h('td', {}, r.assists), h('td', {}, r.steals), h('td', {}, r.blocks), h('td', {}, r.turnovers),
          h('td', {}, `${r.fgm}/${r.fga}`), h('td', {}, `${r.tpm}/${r.tpa}`), h('td', {}, `${r.ftm}/${r.fta}`))))))
        : 空表示('まだ記録がありません')));
}

async function 個別スタッツ編集(選手ID, 行) {
  const 入力 = スタッツ入力パネル(行 || {});
  const 保存 = await シート(行 ? 'スタッツを編集' : 'スタッツを追加', (閉じる) => [
    (() => {
      const f = フォーム([
        { 名前: 'date', ラベル: '日付', 種類: 'date', 必須: true },
        { 名前: 'label', ラベル: '試合名', 例: '例：練習試合 vs 北高' },
      ], async (v) => {
        const 本文 = { ...v, ...入力.値() };
        if (行) await api('PUT', `/api/stats/${行.id}`, 本文); else await api('POST', `/api/players/${選手ID}/stats`, 本文);
        閉じる(true);
      }, { 値: 行 || { date: 今日の日付() } });
      f.insertBefore(入力.要素, f.querySelector('button[type=submit]'));
      return f;
    })(),
    行 ? h('button', {
      class: 'ボタン 危険 大',
      onclick: async () => { if (await 確認('この記録を削除しますか？', '削除', true)) { await api('DELETE', `/api/stats/${行.id}`).catch(エラー通知); 閉じる(true); } },
    }, 'この記録を削除') : null,
  ]);
  if (保存) { 通知('保存しました'); 選択タブ = 'スタッツ'; 選手カルテ画面(選手ID); }
}

async function 成長記録タブ(k, id, 本人, 中身) {
  const データ = await api('GET', `/api/players/${id}/calendar?month=${表示月}`);
  const 詳細 = h('div', { class: '日の詳細' });
  const 月を動かす = (量) => {
    const [y, m] = 表示月.split('-').map(Number);
    const d = new Date(y, m - 1 + 量, 1);
    表示月 = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    成長記録タブ(k, id, 本人, 中身);
  };
  const 日を表示 = (日) => {
    置き換え(詳細, 
      h('h3', {}, 日付表示(日.date)),
      日.attended.length || 日.steps.length || 日.self_practice.length ? h('ul', { class: '箇条' },
        日.attended.map((a) => h('li', {}, `🏀 ${a.title}（${a.status}）`)),
        日.steps.map((st) => h('li', {}, `🪜 ${st.title}${st.cleared ? '（クリア！）' : ''}`)),
        日.self_practice.map((p) => h('li', {}, `💪 自主練 ${p.minutes}分：${p.content} `,
          h('button', { class: '小リンク', onclick: async () => { if (await 確認('この自主練の記録を削除しますか？', '削除', true)) { await api('DELETE', `/api/practice-logs/${p.id}`).catch(エラー通知); 成長記録タブ(k, id, 本人, 中身); } } }, '削除')))) : 空表示('記録はありません'),
      h('button', { class: 'ボタン 控えめ', onclick: () => 自主練を記録(日.date) }, '＋ この日の自主練を記録'));
  };
  const 自主練を記録 = async (日付) => {
    const 保存 = await シート('自主練を記録', (閉じる) => フォーム([
      { 名前: 'date', ラベル: '日付', 種類: 'date', 必須: true },
      { 名前: 'minutes', ラベル: '時間（分）', 種類: 'number', 最小: 1, 最大値: 600, 必須: true, 入力モード: 'numeric' },
      { 名前: 'content', ラベル: '内容', 必須: true, 例: '例：シュート100本・体幹' },
    ], async (v) => { await api('POST', `/api/players/${id}/practice-logs`, v); 閉じる(true); }, { 値: { date: 日付 || 今日の日付(), minutes: 30 } }));
    if (保存) { 通知('記録しました 💪'); 成長記録タブ(k, id, 本人, 中身); }
  };
  const [y, m] = 表示月.split('-').map(Number);
  置き換え(中身, 
    h('section', { class: 'カード' },
      h('div', { class: '期間移動' },
        h('button', { class: 'ボタン 控えめ 小', onclick: () => 月を動かす(-1) }, '‹'),
        h('strong', {}, `${y}年${m}月`),
        h('button', { class: 'ボタン 控えめ 小', onclick: () => 月を動かす(1) }, '›')),
      h('div', { class: '数値タイル' }, タイル('活動した日', `${データ.active_days}日`), タイル('最長連続', `${データ.longest_streak}日`), タイル('自主練', `${データ.self_practice_minutes}分`)),
      月カレンダー(データ, 日を表示),
      h('div', { class: '凡例' },
        h('span', {}, h('i', { class: '印 練習' }), '練習参加'),
        h('span', {}, h('i', { class: '印 ステップ' }), 'ステップ練習'),
        h('span', {}, h('i', { class: '印 自主練' }), '自主練')),
      詳細),
    h('button', { class: 'ボタン 大', onclick: () => 自主練を記録(null) }, '💪 今日の自主練を記録'));
  const 今日 = データ.days.find((d) => d.date === 今日の日付());
  if (今日) 日を表示(今日);
}

async function フィードバックタブ(k, id, 本人, 中身) {
  const 一覧 = await api('GET', `/api/players/${id}/feedback`);
  const 送る = async () => {
    const 保存 = await シート('フィードバックを送る', (閉じる) => フォーム([
      { 名前: 'body', ラベル: 'コメント', 種類: 'textarea', 行数: 5, 必須: true, 例: '良かった点・次に意識すること' },
    ], async (v) => { await api('POST', `/api/players/${id}/feedback`, v); 閉じる(true); }, { 送信文言: '送信' }));
    if (保存) { 通知('送信しました'); フィードバックタブ(k, id, 本人, 中身); }
  };
  const 確認する = async (f) => {
    const 保存 = await シート('確認しました', (閉じる) => フォーム([
      { 名前: 'reply', ラベル: '返信（任意）', 種類: 'textarea', 例: '例：次の練習で意識します！' },
    ], async (v) => { await api('POST', `/api/feedback/${f.id}/confirm`, v); 閉じる(true); }, { 送信文言: '確認済みにする' }));
    if (保存) フィードバックタブ(k, id, 本人, 中身);
  };
  置き換え(中身, 
    コーチか() ? h('button', { class: 'ボタン 大', onclick: 送る }, '✏️ フィードバックを送る') : null,
    一覧.length ? h('div', { class: 'リスト' }, 一覧.map((f) => h('section', { class: `カード ${!f.confirmed_at && 本人 ? '強調枠' : ''}` },
      h('div', { class: '行 間' }, h('small', {}, `${f.coach_name || 'コーチ'} ・ ${日時表示(f.created_at)}`),
        f.confirmed_at ? バッジ('確認済み', '良') : バッジ('未確認', '注意')),
      h('p', { class: '本文' }, f.body),
      f.reply ? h('p', { class: '返信' }, `↳ ${f.reply}`) : null,
      本人 && !f.confirmed_at ? h('button', { class: 'ボタン', onclick: () => 確認する(f) }, '確認した') : null,
      コーチか() ? h('button', {
        class: '小リンク',
        onclick: async () => { if (await 確認('このフィードバックを削除しますか？', '削除', true)) { await api('DELETE', `/api/feedback/${f.id}`).catch(エラー通知); フィードバックタブ(k, id, 本人, 中身); } },
      }, '削除') : null))) : 空表示('フィードバックはまだありません'));
}

// ---------- スタッツ入力 ----------

const 数値項目 = [
  ['rebounds', 'リバウンド'], ['assists', 'アシスト'], ['steals', 'スティール'], ['blocks', 'ブロック'], ['turnovers', 'ターンオーバー'],
  ['fgm', 'FG成功'], ['fga', 'FG試投'], ['tpm', '3P成功'], ['tpa', '3P試投'], ['ftm', 'FT成功'], ['fta', 'FT試投'], ['minutes', '出場時間(分)'],
];

// カウンター（＋／−）とシュートチャートのタップで入力するパネル
function スタッツ入力パネル(初期 = {}) {
  const 値 = Object.fromEntries(数値項目.map(([k]) => [k, Number(初期[k] || 0)]));
  const エリア = structuredClone(初期.zones || {});
  let 選択エリア = null;
  const 得点表示 = h('strong', { class: '得点表示' });
  const カウンター欄 = h('div', { class: 'カウンター一覧' });
  const チャート欄 = h('div', {});
  const 操作欄 = h('div', { class: 'ボタン列' });

  const 得点 = () => (値.fgm - 値.tpm) * 2 + 値.tpm * 3 + 値.ftm;
  const 更新 = () => {
    得点表示.textContent = `${得点()} 点`;
    置き換え(カウンター欄, ...数値項目.map(([k, 名前]) => h('div', { class: 'カウンター' },
      h('span', {}, 名前),
      h('button', { type: 'button', class: 'アイコンボタン', 'aria-label': `${名前}を減らす`, onclick: () => { 値[k] = Math.max(0, 値[k] - 1); 整合(k, -1); 更新(); } }, '−'),
      h('strong', {}, 値[k]),
      h('button', { type: 'button', class: 'アイコンボタン 強', 'aria-label': `${名前}を増やす`, onclick: () => { 値[k] += 1; 整合(k, 1); 更新(); } }, '＋'))));
    const 一覧 = Object.keys(エリア位置).map((z) => ({ zone: z, a: エリア[z]?.a || 0, m: エリア[z]?.m || 0 }));
    置き換え(チャート欄, シュートチャート(一覧, { 選択中: 選択エリア, 選択時: (z) => { 選択エリア = z; 更新(); } }));
    置き換え(操作欄, 選択エリア
      ? [h('span', { class: '伸びる' }, 選択エリア),
        h('button', { type: 'button', class: 'ボタン 良', onclick: () => シュート(true) }, '⭕ 成功'),
        h('button', { type: 'button', class: 'ボタン 悪', onclick: () => シュート(false) }, '❌ 失敗'),
        h('button', { type: 'button', class: 'ボタン 控えめ', onclick: () => 取消() }, '取消')]
      : h('small', {}, 'コートのエリアをタップ → 成功／失敗 でシュートを記録（FG・3Pにも自動で加算）'));
  };
  // 成功を増やしたら試投も増やす、試投を減らしたら成功も減らす（矛盾しないように）
  const 整合 = (k, 増減) => {
    const 組 = { fgm: 'fga', tpm: 'tpa', ftm: 'fta' };
    const 逆 = { fga: 'fgm', tpa: 'tpm', fta: 'ftm' };
    if (増減 > 0 && 組[k] && 値[組[k]] < 値[k]) 値[組[k]] = 値[k];
    if (増減 < 0 && 逆[k] && 値[逆[k]] > 値[k]) 値[逆[k]] = 値[k];
    if (増減 > 0 && (k === 'tpm' || k === 'tpa')) { 値.fgm = Math.max(値.fgm, 値.tpm); 値.fga = Math.max(値.fga, 値.tpa); }
  };
  const シュート = (成功) => {
    const z = (エリア[選択エリア] ||= { a: 0, m: 0 });
    z.a += 1;
    値.fga += 1;
    if (成功) { z.m += 1; 値.fgm += 1; }
    if (選択エリア.startsWith('3P')) { 値.tpa += 1; if (成功) 値.tpm += 1; }
    更新();
  };
  const 取消 = () => {
    const z = エリア[選択エリア];
    if (!z || !z.a) return;
    const 成功だった = z.m > 0 && z.m === z.a ? true : z.m > 0 && window.confirm('成功を1本取り消しますか？（キャンセルで失敗を1本取り消し）');
    z.a -= 1;
    値.fga = Math.max(0, 値.fga - 1);
    if (成功だった) { z.m -= 1; 値.fgm = Math.max(0, 値.fgm - 1); }
    if (選択エリア.startsWith('3P')) { 値.tpa = Math.max(0, 値.tpa - 1); if (成功だった) 値.tpm = Math.max(0, 値.tpm - 1); }
    更新();
  };
  更新();
  return {
    要素: h('div', { class: 'スタッツ入力' }, h('div', { class: '行 間' }, h('span', {}, '得点（自動計算）'), 得点表示), チャート欄, 操作欄, カウンター欄),
    値: () => ({ ...値, points: null, zones: エリア }),
  };
}

export async function スタッツ入力画面() {
  const メンバー = (await api('GET', '/api/members')).filter((m) => m.role === 'player');
  const 入力中 = new Map(); // 選手ID → パネル
  let 選択 = null;
  const 選手欄 = h('div', { class: 'チップ列' });
  const パネル欄 = h('div', {});
  const 日付 = h('input', { type: 'date', value: 今日の日付(), 'aria-label': '日付' });
  const 試合名 = h('input', { type: 'text', placeholder: '試合名（例：練習試合 vs 北高）', maxLength: 60, 'aria-label': '試合名' });

  const 更新 = () => {
    置き換え(選手欄, ...メンバー.map((m) => h('button', {
      class: `チップ ${選択 === m.id ? '選択中' : ''} ${入力中.has(m.id) ? '入力済' : ''}`,
      onclick: () => { 選択 = m.id; if (!入力中.has(m.id)) 入力中.set(m.id, スタッツ入力パネル()); 更新(); },
    }, m.number ? `#${m.number} ` : '', m.name.split(' ').pop())));
    置き換え(パネル欄, 選択 ? h('section', { class: 'カード' },
      h('div', { class: '行 間' },
        h('h2', {}, メンバー.find((m) => m.id === 選択).name),
        h('button', { class: '小リンク', onclick: () => { 入力中.delete(選択); 選択 = null; 更新(); } }, 'この選手の入力をやめる')),
      入力中.get(選択).要素) : 空表示('選手を選んでください（出場した選手を順に入力）'));
  };
  更新();
  描画(
    見出し('スタッツ入力', null, '#/players'),
    h('section', { class: 'カード' }, h('div', { class: '項目' }, h('label', {}, '日付'), 日付), h('div', { class: '項目' }, h('label', {}, '試合名'), 試合名)),
    選手欄,
    パネル欄,
    h('button', {
      class: 'ボタン 大',
      onclick: async () => {
        if (!入力中.size) return 通知('入力した選手がいません', '注意');
        const rows = [...入力中.entries()].map(([player_id, パネル]) => ({ player_id, ...パネル.値() }));
        try {
          await api('POST', '/api/stats/game', { date: 日付.value, label: 試合名.value, rows });
          通知(`${rows.length}人分のスタッツを保存しました`);
          location.hash = '#/stats/team';
        } catch (エラー) { エラー通知(エラー); }
      },
    }, '💾 まとめて保存'));
}

// ---------- チームスタッツ ----------

let 並び替え = 'points';

export async function チームスタッツ画面() {
  const 一覧 = await api('GET', '/api/stats/team');
  const 列 = [['points', '得点'], ['rebounds', 'RB'], ['assists', 'AS'], ['steals', 'ST'], ['blocks', 'BK'], ['turnovers', 'TO'], ['fg_pct', 'FG%'], ['tp_pct', '3P%'], ['ft_pct', 'FT%']];
  const 値 = (r, k) => (k.endsWith('_pct') ? r[k] : r.averages[k]);
  const 並び = [...一覧].sort((a, b) => (値(b, 並び替え) ?? -1) - (値(a, 並び替え) ?? -1));
  描画(
    見出し('チームスタッツ', コーチか() ? h('a', { class: 'ボタン 小', href: '#/stats/entry' }, '＋ 入力') : null, '#/more'),
    オフライン注記(一覧),
    h('p', { class: '補足' }, '1試合平均。列名をタップすると並び替えできます'),
    h('div', { class: '表の枠 カード' }, h('table', { class: '表' },
      h('thead', {}, h('tr', {}, h('th', {}, '選手'), h('th', {}, '試合'),
        列.map(([k, 名前]) => h('th', { class: `押せる ${並び替え === k ? '並び中' : ''}`, onclick: () => { 並び替え = k; チームスタッツ画面(); } }, 名前)))),
      h('tbody', {}, 並び.map((r) => h('tr', {},
        h('td', {}, コーチか() || r.player.id === 状態.ユーザー.id ? h('a', { href: `#/karte/${r.player.id}` }, r.player.number ? `#${r.player.number} ` : '', r.player.name) : [r.player.number ? `#${r.player.number} ` : '', r.player.name]),
        h('td', {}, r.games),
        列.map(([k]) => h('td', { class: 並び替え === k ? '並び中' : '' }, r.games ? (k.endsWith('_pct') ? 率(値(r, k)) : 値(r, k)) : '—'))))))));
}
