// 練習メニュー（ドリルのテンプレート）の一覧・登録・編集

import { api, 置き換え, h, 描画, 見出し, コーチか, 日付表示, 空表示, 通知, エラー通知, 確認, シート, フォーム, オフライン注記 } from './共通.js';

const 項目 = [
  { 名前: 'name', ラベル: 'ドリル名', 必須: true },
  { 名前: 'category', ラベル: '分類', 例: '例：シュート／ディフェンス／ウォームアップ' },
  { 名前: 'purpose', ラベル: '目的' },
  { 名前: 'minutes', ラベル: '所要時間（分）', 種類: 'number', 最小: 0, 最大値: 600, 入力モード: 'numeric' },
  { 名前: 'equipment', ラベル: '使用道具', 例: '例：ボール・コーン・ビブス' },
  { 名前: 'description', ラベル: 'やり方・ポイント', 種類: 'textarea', 行数: 5 },
];

async function 編集(メニュー = null) {
  const 保存した = await シート(メニュー ? 'メニューを編集' : 'メニューを登録', (閉じる) => [
    フォーム(項目, async (値) => {
      if (メニュー) await api('PUT', `/api/menus/${メニュー.id}`, 値);
      else await api('POST', '/api/menus', 値);
      閉じる(true);
    }, { 値: メニュー || { minutes: 10 } }),
    メニュー ? h('button', {
      class: 'ボタン 危険 大',
      onclick: async () => {
        if (!(await 確認(`「${メニュー.name}」を削除しますか？過去の練習からも外れます。`, '削除', true))) return;
        try { await api('DELETE', `/api/menus/${メニュー.id}`); 閉じる(true); } catch (エラー) { エラー通知(エラー); }
      },
    }, '削除') : null,
  ]);
  if (保存した) { 通知('保存しました'); 練習メニュー画面(); }
}

export async function 練習メニュー画面() {
  const メニュー = await api('GET', '/api/menus');
  const 検索 = h('input', { type: 'search', placeholder: '名前・分類・目的・道具で絞り込み', 'aria-label': '絞り込み' });
  const 一覧 = h('div', {});
  const 描く = () => {
    const q = 検索.value.trim();
    const 対象 = メニュー.filter((m) => !q || `${m.name}${m.category}${m.purpose}${m.equipment}`.includes(q));
    const 分類別 = {};
    for (const m of 対象) (分類別[m.category || '未分類'] ||= []).push(m);
    置き換え(一覧, ...(対象.length ? Object.entries(分類別).map(([分類, 件]) => h('section', { class: 'カード' },
      h('h2', {}, 分類),
      件.map((m) => h('details', { class: 'メニュー詳細' },
        h('summary', {}, h('strong', {}, m.name), h('span', { class: '分' }, `${m.minutes}分`)),
        m.purpose ? h('p', {}, `🎯 ${m.purpose}`) : null,
        m.equipment ? h('p', {}, `🧰 ${m.equipment}`) : null,
        m.description ? h('p', { class: '本文' }, m.description) : null,
        h('p', { class: '補足' }, `使用 ${m.used_count}回`, m.last_used ? ` ・ 最終 ${日付表示(m.last_used)}` : ''),
        h('div', { class: 'ボタン列' },
          h('a', { class: 'ボタン 控えめ 小', href: `#/history?menu=${m.id}` }, '使った練習'),
          コーチか() ? h('button', { class: 'ボタン 控えめ 小', onclick: () => 編集(m) }, '編集') : null))))) : [空表示('メニューがありません')]));
  };
  検索.addEventListener('input', 描く);
  描く();
  描画(
    見出し('練習メニュー', コーチか() ? h('button', { class: 'ボタン 小', onclick: () => 編集() }, '＋ 登録') : null, '#/more'),
    オフライン注記(メニュー),
    h('p', { class: '補足' }, 'よく使うドリルをテンプレートとして登録し、予定を作るときに呼び出せます。'),
    検索,
    一覧);
}
