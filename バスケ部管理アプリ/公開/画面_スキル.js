// スキル診断：能力値（コーチ評価・自己評価・スタッツ自動算出）→ レベル判定 → 次に取り組むステップ練習の提示
// ステップ進行一覧（コーチ）・ステップドリル管理（コーチ）

import {
  api, h, 描画, 見出し, コーチか, 状態, バッジ, 空表示, 通知, エラー通知, 確認, シート, フォーム, 日付表示, 日時表示, 今日の日付, オフライン注記,
} from './共通.js';
import { レーダーチャート, 進捗バー } from './図表.js';

const レベルの色 = { 初級: '薄', 中級: '注意', 上級: '良', 未診断: '薄' };
const 状態の印 = { 完了: '✅', 実施中: '▶️', 未着手: '⬜' };

async function 能力値を入力(選手ID, 診断) {
  const 評価元 = コーチか() ? 'コーチ評価' : '自己評価';
  const 保存 = await シート(`${評価元}を入力`, (閉じる) => {
    const 入力 = {};
    const 行一覧 = 診断.map((d) => {
      const 前回 = コーチか() ? d.coach : d.self;
      const 表示 = h('strong', { class: '値' });
      const 範囲 = h('input', { type: 'range', min: 0, max: 100, step: 5, value: 前回 ?? 50, 'aria-label': d.name });
      const 更新 = () => {
        表示.textContent = 前回 === null && !入力[d.category_id].変更 ? '未評価'
          : `${範囲.value}（${範囲.value >= 70 ? '上級' : 範囲.value >= 40 ? '中級' : '初級'}）${入力[d.category_id].変更 ? '' : ' 前回'}`;
      };
      入力[d.category_id] = { 範囲, 変更: false };
      範囲.addEventListener('input', () => { 入力[d.category_id].変更 = true; 更新(); });
      更新();
      return h('div', { class: '評価行' }, h('div', { class: '行 間' }, h('span', {}, d.name), 表示), 範囲);
    });
    return [
      h('p', { class: '補足' }, '0〜100で評価します。目安：40未満＝初級、40〜69＝中級、70以上＝上級'),
      ...行一覧,
      h('button', {
        class: 'ボタン 大',
        onclick: async () => {
          // 動かしたスキルだけ記録する（触っていないスキルに仮の値が入らないように）
          const items = Object.entries(入力).filter(([, x]) => x.変更).map(([category_id, x]) => ({ category_id: Number(category_id), value: Number(x.範囲.value) }));
          if (!items.length) { 通知('スライダーを動かして評価してください', '注意'); return; }
          try { await api('POST', `/api/players/${選手ID}/assessments`, { items }); 閉じる(true); } catch (エラー) { エラー通知(エラー); }
        },
      }, '保存'),
    ];
  });
  if (保存) { 通知('保存しました。次の練習メニューを更新しました'); スキル画面(選手ID); }
}

async function 完了報告(選手ID, ドリル) {
  const 結果 = await シート('練習の報告', (閉じる) => [
    h('p', {}, h('strong', {}, ドリル.title)),
    ドリル.clear_condition ? h('p', { class: 'クリア条件' }, `🏁 クリア条件：${ドリル.clear_condition}`) : null,
    フォーム([
      { 名前: 'self_rating', ラベル: '自己評価（1〜5）', 種類: 'select', 選択肢: [[5, '★★★★★ 完璧'], [4, '★★★★ よくできた'], [3, '★★★ まあまあ'], [2, '★★ いまいち'], [1, '★ できなかった']], 既定: 3 },
      { 名前: 'cleared', ラベル: 'クリア条件を満たした（次のステップへ進む）', 種類: 'checkbox' },
      { 名前: 'comment', ラベル: 'ふりかえり', 種類: 'textarea', 例: '例：10本中8本成功。左手がまだ不安定' },
      { 名前: 'video_url', ラベル: '動画のURL（任意）', 種類: 'url', 例: 'https://...', 補足: 'スマホで撮った動画をGoogleドライブ等にアップしてURLを貼り付け' },
      { 名前: 'date', ラベル: '実施日', 種類: 'date' },
    ], async (v) => {
      const r = await api('POST', `/api/players/${選手ID}/steps/report`, { ...v, self_rating: Number(v.self_rating), drill_id: ドリル.id });
      閉じる(r);
    }, { 送信文言: '報告する', 値: { date: 今日の日付() } }),
  ]);
  if (!結果) return;
  if (結果.cleared) 通知(結果.next ? `🎉 クリア！次は「${結果.next.title}」` : '🎉 クリア！このスキルのステップをすべて達成しました');
  else 通知('報告しました。クリアまでがんばろう！');
  スキル画面(選手ID);
}

function ドリルカード(選手ID, 推奨, { 報告できる }) {
  const d = 推奨.drill;
  return h('section', { class: `カード ステップカード ${推奨.priority ? '優先' : ''}` },
    h('div', { class: '行 間' },
      h('small', {}, `${推奨.category_name} ・ ${d.level} ・ ステップ ${d.order}/${推奨.total}`),
      h('div', { class: 'バッジ列' },
        推奨.priority ? バッジ(`優先${推奨.priority}`, '強調') : null,
        推奨.overridden ? バッジ('コーチ指定', '味方') : null,
        バッジ(d.status, d.status === '実施中' ? '注意' : '薄'))),
    h('h3', {}, d.title),
    推奨.override_note ? h('p', { class: '返信' }, `💬 ${推奨.override_note}`) : null,
    d.content ? h('p', { class: '本文' }, d.content) : null,
    h('p', { class: '補足' }, `⏱ 目安 ${d.minutes}分`, d.clear_condition ? ` ・ 🏁 ${d.clear_condition}` : ''),
    進捗バー(推奨.completed, 推奨.total),
    報告できる ? h('button', { class: 'ボタン 大', onclick: () => 完了報告(選手ID, d) }, '✍️ やったので報告する') : null);
}

async function ステップを調整(選手ID, カテゴリ, ステップ) {
  const 選択 = await シート(ステップ.title, (閉じる) => [
    h('p', { class: '補足' }, `${カテゴリ.category_name} ・ ${ステップ.level} ・ 現在：${ステップ.status}`),
    h('button', { class: 'ボタン 大', onclick: () => 閉じる('提示') }, '👉 この練習を提示する（自動提示を上書き）'),
    ステップ.status !== '完了' ? h('button', { class: 'ボタン 控えめ 大', onclick: () => 閉じる('完了') }, '✅ 完了にする') : null,
    ステップ.status !== '未着手' ? h('button', { class: 'ボタン 控えめ 大', onclick: () => 閉じる('未着手') }, '↩️ 未着手に戻す') : null,
    カテゴリ.override ? h('button', { class: 'ボタン 控えめ 大', onclick: () => 閉じる('解除') }, '🔄 コーチ指定を解除して自動提示に戻す') : null,
  ]);
  try {
    if (選択 === '提示') {
      const メモ = await シート('選手へのひとこと', (閉じる) => フォーム([{ 名前: 'note', ラベル: 'メモ（任意）', 例: '例：試合でミスが多かったので基礎から' }], async (v) => 閉じる(v.note), { 送信文言: '提示する' }));
      if (メモ === undefined) return;
      await api('PUT', `/api/players/${選手ID}/steps/override`, { category_id: カテゴリ.category_id, drill_id: ステップ.id, note: メモ });
    } else if (選択 === '解除') {
      await api('PUT', `/api/players/${選手ID}/steps/override`, { category_id: カテゴリ.category_id, drill_id: null });
    } else if (選択) {
      await api('PUT', `/api/players/${選手ID}/steps/status`, { drill_id: ステップ.id, status: 選択 });
    } else return;
    通知('更新しました');
    スキル画面(選手ID);
  } catch (エラー) { エラー通知(エラー); }
}

export async function スキル画面(id) {
  const [スキル, ステップ, 選手] = await Promise.all([
    api('GET', `/api/players/${id}/skills`), api('GET', `/api/players/${id}/steps`), api('GET', `/api/members/${id}`),
  ]);
  const 本人 = 状態.ユーザー.id === id;
  const コーチ = コーチか();
  const 診断 = スキル.diagnosis;
  const 名前 = 診断.map((d) => d.name);
  const 診断済み = 診断.some((d) => d.value !== null);
  const 差の警告 = 診断.filter((d) => d.gap_warning);

  描画(
    見出し(本人 ? 'スキル診断' : `${選手.name} のスキル`, null, コーチ ? '#/players' : '#/karte'),
    オフライン注記(スキル),
    h('section', { class: 'カード' },
      h('div', { class: '行 間' }, h('h2', {}, '🧭 能力値'), h('button', { class: 'ボタン 小', onclick: () => 能力値を入力(id, 診断) }, コーチ ? 'コーチ評価を入力' : '自己評価を入力')),
      診断済み ? レーダーチャート(名前, [
        { 名前: '総合', 値: 診断.map((d) => d.value), 色: 'var(--系列1)', 塗り: 0.25 },
        { 名前: 'コーチ', 値: 診断.map((d) => d.coach), 色: 'var(--系列2)', 塗り: 0, 破線: true },
        { 名前: '自己評価', 値: 診断.map((d) => d.self), 色: 'var(--系列3)', 塗り: 0, 破線: true },
        { 名前: 'スタッツ', 値: 診断.map((d) => d.stats), 色: 'var(--系列4)', 塗り: 0, 破線: true },
      ]) : 空表示('まだ診断されていません。評価を入力するとレーダーチャートと次の練習が表示されます'),
      h('div', { class: '表の枠' }, h('table', { class: '表 スキル表' },
        h('thead', {}, h('tr', {}, ['スキル', '総合', 'レベル', 'コーチ', '自己', 'スタッツ'].map((c) => h('th', {}, c)))),
        h('tbody', {}, 診断.map((d) => h('tr', {},
          h('td', {}, d.name, d.priority ? バッジ(`優先${d.priority}`, '強調') : null),
          h('td', {}, h('strong', {}, d.value ?? '—')),
          h('td', {}, バッジ(d.level, レベルの色[d.level])),
          h('td', {}, d.coach ?? '—'), h('td', {}, d.self ?? '—'), h('td', {}, d.stats ?? '—')))))),
      h('small', {}, `総合＝コーチ${スキル.weights['コーチ'] * 100}%・スタッツ${スキル.weights['スタッツ'] * 100}%・自己評価${スキル.weights['自己評価'] * 100}%（入力された分だけで計算）`),
      差の警告.length ? h('p', { class: '注意書き' }, `⚠️ 自己評価とコーチ評価に大きな差があります：${差の警告.map((d) => `${d.name}（${d.gap > 0 ? '自己評価が高め' : '自己評価が低め'}）`).join('、')}。コーチと話してみよう`) : null),

    h('h2', { class: '節見出し' }, '🪜 次に取り組む練習'),
    ステップ.recommendations.length
      ? ステップ.recommendations.slice(0, 3).map((r) => ドリルカード(id, r, { 報告できる: 本人 || コーチ }))
      : h('div', { class: 'カード' }, 空表示('提示できる練習がありません（すべて達成、またはドリル未登録）')),
    ステップ.recommendations.length > 3 ? h('details', { class: 'カード' },
      h('summary', {}, `ほかのスキルの練習（${ステップ.recommendations.length - 3}件）`),
      ステップ.recommendations.slice(3).map((r) => ドリルカード(id, r, { 報告できる: 本人 || コーチ }))) : null,

    h('section', { class: 'カード' },
      h('h2', {}, '📶 スキル別のステップ'),
      コーチ ? h('small', {}, 'ステップをタップすると、提示の上書き・完了・やり直しができます') : null,
      ステップ.categories.map((c) => h('details', { class: 'ステップ階段' },
        h('summary', {},
          h('strong', {}, c.category_name), ' ',
          バッジ(c.diagnosis.level, レベルの色[c.diagnosis.level]),
          h('span', { class: '数' }, `${c.completed}/${c.total}`)),
        h('ol', {}, c.steps.map((st) => h('li', { class: `${st.is_current ? '現在' : ''} ${st.status}` },
          h(コーチ ? 'button' : 'div', { class: 'ステップ行', onclick: コーチ ? () => ステップを調整(id, c, st) : null },
            h('span', { 'aria-hidden': 'true' }, 状態の印[st.status]),
            h('span', { class: '伸びる' }, h('small', {}, st.level), ' ', st.title),
            st.is_current ? バッジ('今ここ', '強調') : null))))))),

    ステップ.reports.length ? h('section', { class: 'カード' },
      h('h2', {}, '📝 報告の記録'),
      h('div', { class: 'リスト' }, ステップ.reports.map((r) => h('div', { class: 'リスト項目 縦' },
        h('div', { class: '行 間' }, h('strong', {}, `${r.category_name}：${r.title}`), r.cleared ? バッジ('クリア', '良') : バッジ('継続', '薄')),
        h('small', {}, `${日付表示(r.date)} ・ ${'★'.repeat(r.self_rating)}${'☆'.repeat(5 - r.self_rating)}`),
        r.comment ? h('p', {}, r.comment) : null,
        r.video_url ? h('a', { href: r.video_url, target: '_blank', rel: 'noopener noreferrer' }, '🎬 動画を見る') : null)))) : null,

    スキル.history.length ? h('details', { class: 'カード' },
      h('summary', {}, '評価の履歴'),
      h('div', { class: 'リスト' }, スキル.history.map((a) => h('div', { class: 'リスト項目' },
        h('div', { class: '伸びる' }, h('strong', {}, `${a.category_name}：${a.value}`), h('small', {}, `${a.source} ・ ${a.assessor_name || ''} ・ ${日時表示(a.assessed_at)}`)))))) : null);
}

// ---------- ステップ進行一覧（コーチ） ----------

export async function ステップ一覧表画面() {
  const データ = await api('GET', '/api/steps/overview');
  描画(
    見出し('ステップ進行一覧', null, '#/players'),
    h('p', { class: '補足' }, '各マスは「現在のレベル・ステップ（完了数/全体）」。★は優先して伸ばすスキル、👉はコーチ指定。選手名をタップで詳細'),
    データ.players.length ? h('div', { class: '表の枠 カード' }, h('table', { class: '表 一覧表' },
      h('thead', {}, h('tr', {}, h('th', { class: '固定列' }, '選手'), データ.categories.map((c) => h('th', {}, c.name)), h('th', {}, '最終報告'))),
      h('tbody', {}, データ.players.map((p) => h('tr', {},
        h('td', { class: '固定列' }, h('a', { href: `#/skills/${p.player.id}` }, p.player.number ? `#${p.player.number} ` : '', p.player.name)),
        p.categories.map((c) => h('td', { class: `マス ${c.priority ? '優先' : ''}` },
          c.current ? [h('small', {}, c.current.level), h('div', {}, `S${c.current.order}`, c.priority ? ' ★' : '', c.overridden ? ' 👉' : '')] : h('div', {}, '🏆'),
          h('small', { class: '数' }, `${c.completed}/${c.total}`))),
        h('td', {}, p.last_report ? 日付表示(p.last_report) : '—')))))) : 空表示('選手がいません'));
}

// ---------- ドリル管理（コーチ） ----------

async function ドリル編集(カテゴリ一覧, ドリル一覧, 既存 = null, 初期 = {}) {
  const 保存 = await シート(既存 ? 'ドリルを編集' : 'ドリルを追加', (閉じる) => [
    フォーム([
      { 名前: 'category_id', ラベル: 'スキル', 種類: 'select', 選択肢: カテゴリ一覧.map((c) => [c.id, c.name]) },
      { 名前: 'level', ラベル: 'レベル', 種類: 'select', 選択肢: ['初級', '中級', '上級'] },
      { 名前: 'step_no', ラベル: 'レベル内の順番', 種類: 'number', 最小: 1, 最大値: 100, 入力モード: 'numeric' },
      { 名前: 'title', ラベル: 'ドリル名', 必須: true },
      { 名前: 'content', ラベル: 'やり方', 種類: 'textarea', 行数: 4 },
      { 名前: 'minutes', ラベル: '目安時間（分）', 種類: 'number', 最小: 0, 最大値: 300, 入力モード: 'numeric' },
      { 名前: 'clear_condition', ラベル: 'クリア条件', 例: '例：10本中7本成功' },
      { 名前: 'next_step_id', ラベル: '次のステップ', 種類: 'select', 選択肢: [['', '（自動：レベル・順番どおり）'], ...ドリル一覧.filter((d) => d.id !== 既存?.id).map((d) => [d.id, `${d.category_name}・${d.level}：${d.title}`])] },
    ], async (v) => {
      const 本文 = { ...v, category_id: Number(v.category_id), next_step_id: v.next_step_id ? Number(v.next_step_id) : null, insert_after_id: 初期.insert_after_id };
      if (既存) await api('PUT', `/api/drills/${既存.id}`, 本文); else await api('POST', '/api/drills', 本文);
      閉じる(true);
    }, { 値: 既存 || { minutes: 10, step_no: 1, level: '初級', ...初期 } }),
    既存 ? h('button', {
      class: 'ボタン 危険 大',
      onclick: async () => {
        if (!(await 確認(`「${既存.title}」を削除しますか？前後のステップはつなぎ直されます。`, '削除', true))) return;
        try { await api('DELETE', `/api/drills/${既存.id}`); 閉じる(true); } catch (エラー) { エラー通知(エラー); }
      },
    }, '削除') : null,
  ]);
  if (保存) { 通知('保存しました'); ドリル管理画面(); }
}

export async function ドリル管理画面() {
  const [カテゴリ, ドリル] = await Promise.all([api('GET', '/api/skill-categories'), api('GET', '/api/drills')]);
  const スキル追加 = async () => {
    const 名前 = await シート('スキルを追加', (閉じる) => フォーム([{ 名前: 'name', ラベル: 'スキル名', 必須: true, 例: '例：フットワーク' }], async (v) => 閉じる(v.name)));
    if (!名前) return;
    try { await api('POST', '/api/skill-categories', { name: 名前 }); ドリル管理画面(); } catch (エラー) { エラー通知(エラー); }
  };
  const スキル編集 = async (c) => {
    const 結果 = await シート('スキルを編集', (閉じる) => [
      フォーム([{ 名前: 'name', ラベル: 'スキル名', 必須: true }, { 名前: 'sort', ラベル: '並び順（小さいほど前）', 種類: 'number', 最小: 0, 最大値: 1000 }], async (v) => {
        await api('PUT', `/api/skill-categories/${c.id}`, v);
        閉じる(true);
      }, { 値: c }),
      h('button', {
        class: 'ボタン 危険 大',
        onclick: async () => {
          if (!(await 確認(`「${c.name}」を削除しますか？このスキルのドリル・評価・進捗もすべて消えます。`, '削除', true))) return;
          try { await api('DELETE', `/api/skill-categories/${c.id}`); 閉じる(true); } catch (エラー) { エラー通知(エラー); }
        },
      }, 'スキルを削除'),
    ]);
    if (結果) ドリル管理画面();
  };
  描画(
    見出し('ステップドリル管理', h('button', { class: 'ボタン 小', onclick: スキル追加 }, '＋ スキル'), '#/more'),
    h('p', { class: '補足' }, 'スキル×レベルごとに練習ドリルを段階順に並べます。選手は診断レベルに応じたステップから始まり、クリアすると自動で次のステップへ進みます。'),
    カテゴリ.map((c) => {
      const 件 = ドリル.filter((d) => d.category_id === c.id);
      return h('section', { class: 'カード' },
        h('div', { class: '行 間' }, h('h2', {}, c.name), h('button', { class: 'ボタン 控えめ 小', onclick: () => スキル編集(c) }, '名前・順番')),
        件.length ? h('ol', { class: 'ドリル一覧' }, 件.map((d) => h('li', {},
          h('button', { class: 'ステップ行', onclick: () => ドリル編集(カテゴリ, ドリル, d) },
            バッジ(d.level, レベルの色[d.level]),
            h('span', { class: '伸びる' }, d.title, h('small', {}, ` ${d.minutes}分`)),
            h('span', { class: '矢印' }, '›')),
          h('button', { class: '差し込み', onclick: () => ドリル編集(カテゴリ, ドリル, null, { category_id: c.id, level: d.level, step_no: d.step_no + 1, insert_after_id: d.id }), 'aria-label': 'この後にドリルを追加' }, '＋ この後に追加'))))
          : 空表示('ドリルがありません'),
        h('button', { class: 'ボタン 控えめ', onclick: () => ドリル編集(カテゴリ, ドリル, null, { category_id: c.id, insert_after_id: 件.length ? 件[件.length - 1].id : undefined, level: 件.length ? 件[件.length - 1].level : '初級' }) }, '＋ 最後に追加'));
    }));
}
