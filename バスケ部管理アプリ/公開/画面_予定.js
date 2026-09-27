// 予定：週間・月間カレンダー、予定詳細（出欠・既読・練習メニュー）、予定の作成／編集、練習履歴の検索

import {
  api, 置き換え, h, 描画, 見出し, コーチか, 日付表示, 日時表示, 日付文字列, 今日の日付, バッジ, 出欠の色,
  空表示, 通知, エラー通知, 確認, シート, フォーム, タブ, オフライン注記,
} from './共通.js';

const 出欠 = ['出席', '遅刻', '早退', '欠席'];
let 表示形式 = (() => { try { return localStorage.getItem('schedule_view') || '週'; } catch { return '週'; } })();
let 基準日 = new Date();

function 週の開始(d) {
  const 結果 = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  結果.setDate(結果.getDate() - ((結果.getDay() + 6) % 7)); // 月曜はじまり
  return 結果;
}

function 日を足す(d, 日数) {
  const 結果 = new Date(d);
  結果.setDate(結果.getDate() + 日数);
  return 結果;
}

function 予定の行(e) {
  return h('a', { class: 'リスト項目', href: `#/events/${e.id}` },
    h('span', { class: `種類点 ${e.kind}`, 'aria-hidden': 'true' }),
    h('div', { class: '伸びる' },
      h('strong', {}, e.title, e.published ? null : バッジ('下書き', '薄')),
      h('small', {}, [e.start_time && `${e.start_time}〜${e.end_time}`, e.place, e.total_minutes ? `メニュー${e.menus.length}件・${e.total_minutes}分` : ''].filter(Boolean).join(' ・ '))),
    コーチか() ? h('small', { class: '数' }, `${e.attend_count}人`) : (e.my_status ? バッジ(e.my_status, 出欠の色[e.my_status]) : (e.date >= 今日の日付() ? バッジ('未回答', '強調') : null)));
}

export async function 予定画面() {
  const 形式 = 表示形式;
  let 開始;
  let 終了;
  if (形式 === '週') {
    開始 = 週の開始(基準日);
    終了 = 日を足す(開始, 6);
  } else {
    開始 = new Date(基準日.getFullYear(), 基準日.getMonth(), 1);
    終了 = new Date(基準日.getFullYear(), 基準日.getMonth() + 1, 0);
  }
  const 予定 = await api('GET', `/api/events?from=${日付文字列(開始)}&to=${日付文字列(終了)}`);
  const 日別 = {};
  for (const e of 予定) (日別[e.date] ||= []).push(e);

  const 移動 = (量) => {
    基準日 = 形式 === '週' ? 日を足す(基準日, 7 * 量) : new Date(基準日.getFullYear(), 基準日.getMonth() + 量, 1);
    予定画面();
  };
  const タイトル = 形式 === '週'
    ? `${開始.getMonth() + 1}/${開始.getDate()} 〜 ${終了.getMonth() + 1}/${終了.getDate()}`
    : `${開始.getFullYear()}年${開始.getMonth() + 1}月`;

  let 本体;
  if (形式 === '週') {
    本体 = h('div', { class: '週間' }, Array.from({ length: 7 }, (_, i) => {
      const 日 = 日付文字列(日を足す(開始, i));
      const 今日か = 日 === 今日の日付();
      return h('section', { class: `週の日 ${今日か ? '今日' : ''}` },
        h('h3', {}, 日付表示(日), 今日か ? バッジ('今日', '強調') : null),
        日別[日]?.length ? h('div', { class: 'リスト' }, 日別[日].map(予定の行)) : h('p', { class: '空 小' }, 'オフ'));
    }));
  } else {
    const 空き = (開始.getDay() + 6) % 7;
    const マス = [];
    for (let i = 0; i < 空き; i++) マス.push(h('div', { class: '日 空き' }));
    const 選択中の日 = h('div', { class: '選択日' });
    const 日を選ぶ = (日) => {
      置き換え(選択中の日, 
        h('h3', {}, 日付表示(日)),
        日別[日]?.length ? h('div', { class: 'リスト' }, 日別[日].map(予定の行)) : 空表示('予定はありません'),
        コーチか() ? h('a', { class: 'ボタン 控えめ', href: `#/events/new?date=${日}` }, '＋ この日に予定を追加') : null);
    };
    for (let d = 1; d <= 終了.getDate(); d++) {
      const 日 = 日付文字列(new Date(開始.getFullYear(), 開始.getMonth(), d));
      const 件 = 日別[日] || [];
      マス.push(h('button', { class: `日 ${日 === 今日の日付() ? '今日' : ''}`, onclick: () => 日を選ぶ(日) },
        h('span', { class: '日付数字' }, d),
        h('span', { class: '印列' }, 件.map((e) => h('i', { class: `印 ${e.kind}` })))));
    }
    本体 = h('div', {}, h('div', { class: '月カレンダー' }, ['月', '火', '水', '木', '金', '土', '日'].map((w) => h('div', { class: '曜日' }, w)), マス), 選択中の日);
    const 初期 = 日付文字列(基準日).slice(0, 7) === 今日の日付().slice(0, 7) ? 今日の日付() : 日付文字列(開始);
    日を選ぶ(初期);
  }

  描画(
    見出し('予定', コーチか() ? h('a', { class: 'ボタン 小', href: '#/events/new' }, '＋ 追加') : null),
    オフライン注記(予定),
    タブ([['週', '週間'], ['月', '月間']], 形式, (v) => {
      表示形式 = v;
      try { localStorage.setItem('schedule_view', v); } catch { /* 無視 */ }
      予定画面();
    }),
    h('div', { class: '期間移動' },
      h('button', { class: 'ボタン 控えめ 小', onclick: () => 移動(-1), 'aria-label': '前へ' }, '‹ 前'),
      h('strong', {}, タイトル),
      h('button', { class: 'ボタン 控えめ 小', onclick: () => 移動(1), 'aria-label': '次へ' }, '次 ›')),
    h('button', { class: '小リンク 中央', onclick: () => { 基準日 = new Date(); 予定画面(); } }, '今日に戻る'),
    本体,
    h('div', { class: '凡例 中央' }, ['練習', '試合', 'その他'].map((k) => h('span', {}, h('i', { class: `印 ${k}` }), k))),
    h('a', { class: 'ボタン 控えめ 大', href: '#/history' }, '🗂️ 過去の練習を検索'));
}

export async function 予定詳細画面(id) {
  const e = await api('GET', `/api/events/${id}`);
  const コーチ = コーチか();
  const 回答する = async (状態, コメント = e.my_comment) => {
    try {
      await api('PUT', `/api/events/${id}/attendance`, { status: 状態, comment: コメント });
      通知(`「${状態}」で回答しました`);
      予定詳細画面(id);
    } catch (エラー) { エラー通知(エラー); }
  };
  const 代理入力 = async (m) => {
    const 選択 = await シート(`${m.name} の出欠`, (閉じる) => [
      h('div', { class: 'ボタン列 折返し' }, 出欠.map((st) => h('button', { class: `ボタン ${m.status === st ? '' : '控えめ'}`, onclick: () => 閉じる(st) }, st))),
      h('button', { class: 'ボタン 控えめ 大', onclick: () => 閉じる('') }, '未回答に戻す'),
    ]);
    if (選択 === undefined) return;
    try {
      await api('PUT', `/api/events/${id}/attendance`, { user_id: m.id, status: 選択 || null });
      予定詳細画面(id);
    } catch (エラー) { エラー通知(エラー); }
  };
  const コメント欄 = h('input', { type: 'text', placeholder: 'ひとこと（例：通院のため遅れます）', maxLength: 200, value: e.my_comment || '' });

  描画(
    見出し(e.title, コーチ ? h('a', { class: 'ボタン 小 控えめ', href: `#/events/${id}/edit` }, '編集') : null, '#/schedule'),
    オフライン注記(e),
    h('section', { class: 'カード' },
      h('p', { class: '大きな日付' }, 日付表示(e.date, true), ' ', バッジ(e.kind, e.kind === '試合' ? '強調' : '薄'), e.published ? null : バッジ('下書き（選手には非表示）', '注意')),
      e.start_time ? h('p', {}, `🕒 ${e.start_time}〜${e.end_time}`) : null,
      e.place ? h('p', {}, `📍 ${e.place}`) : null,
      e.notes ? h('p', { class: '本文' }, e.notes) : null),

    e.date >= 今日の日付() || コーチ ? h('section', { class: 'カード' },
      h('h2', {}, 'あなたの出欠'),
      h('div', { class: '出欠ボタン' }, 出欠.map((st) => h('button', {
        class: `ボタン ${e.my_status === st ? 出欠の色[st] : '控えめ'}`, 'aria-pressed': String(e.my_status === st),
        onclick: () => 回答する(st, コメント欄.value),
      }, st))),
      コメント欄,
      e.my_status ? h('small', {}, `現在：${e.my_status}（コメントを変えたら、もう一度ボタンを押してください）`) : null) : null,

    e.menus.length ? h('section', { class: 'カード' },
      h('h2', {}, `🏋️ 練習メニュー（合計${e.total_minutes}分）`),
      h('ol', { class: 'メニュー順' }, e.menus.map((m) => h('li', {},
        h('details', {},
          h('summary', {}, h('strong', {}, m.name), h('span', { class: '分' }, `${m.minutes}分`)),
          m.purpose ? h('p', {}, `🎯 ${m.purpose}`) : null,
          m.equipment ? h('p', {}, `🧰 ${m.equipment}`) : null,
          m.description ? h('p', { class: '本文' }, m.description) : null))))) : null,

    h('section', { class: 'カード' },
      h('h2', {}, '出欠状況'),
      h('div', { class: '集計列' },
        出欠.map((st) => h('div', { class: `集計 ${出欠の色[st]}` }, h('strong', {}, e.summary[st]), h('small', {}, st))),
        h('div', { class: '集計' }, h('strong', {}, e.summary['未回答']), h('small', {}, '未回答')),
        h('div', { class: '集計' }, h('strong', {}, `${e.summary['既読']}/${e.member_count}`), h('small', {}, '既読'))),
      コーチ ? h('small', {}, 'メンバーをタップすると出欠を代理入力できます') : null,
      h('div', { class: 'リスト' }, e.attendance.map((m) => h(コーチ ? 'button' : 'div', {
        class: 'リスト項目', onclick: コーチ ? () => 代理入力(m) : null,
      },
      h('div', { class: '伸びる' },
        h('strong', {}, m.number ? `#${m.number} ` : '', m.name, m.role === 'coach' ? バッジ('コーチ', '薄') : null),
        m.comment ? h('small', {}, m.comment) : null,
        h('small', { class: m.viewed_at ? '既読' : '未読' }, m.viewed_at ? `既読 ${日時表示(m.viewed_at)}` : '未読')),
      m.status ? バッジ(m.status, 出欠の色[m.status]) : バッジ('未回答', '薄'))))),

    コーチ ? h('div', { class: 'ボタン列' },
      h('button', {
        class: 'ボタン 控えめ',
        onclick: async () => {
          const 日付 = await シート('別の日にコピー', (閉じる) => フォーム([{ 名前: 'date', ラベル: 'コピー先の日付', 種類: 'date', 必須: true, 既定: 今日の日付() }], async (v) => 閉じる(v.date), { 送信文言: 'コピー' }));
          if (!日付) return;
          try {
            const 結果 = await api('POST', `/api/events/${id}/copy`, { date: 日付 });
            通知('コピーしました');
            location.hash = `#/events/${結果.id}`;
          } catch (エラー) { エラー通知(エラー); }
        },
      }, '📄 別の日にコピー'),
      h('button', {
        class: 'ボタン 危険',
        onclick: async () => {
          if (!(await 確認('この予定を削除しますか？出欠の記録も消えます。', '削除', true))) return;
          try { await api('DELETE', `/api/events/${id}`); 通知('削除しました'); location.hash = '#/schedule'; } catch (エラー) { エラー通知(エラー); }
        },
      }, '削除')) : null);
}

export async function 予定編集画面(id) {
  const [既存, メニュー] = await Promise.all([id ? api('GET', `/api/events/${id}`) : null, api('GET', '/api/menus')]);
  const 指定日 = new URLSearchParams(location.hash.split('?')[1] || '').get('date');
  let 選択メニュー = 既存 ? 既存.menus.map((m) => m.id) : [];
  const メニュー対応 = Object.fromEntries(メニュー.map((m) => [m.id, m]));
  const メニュー欄 = h('div', { class: 'メニュー選択' });

  const メニュー欄を更新 = () => {
    const 合計 = 選択メニュー.reduce((a, mid) => a + (メニュー対応[mid]?.minutes || 0), 0);
    置き換え(メニュー欄, 
      h('h3', { class: 'フォーム小見出し' }, `練習メニュー（${選択メニュー.length}件・合計${合計}分）`),
      選択メニュー.length ? h('ol', { class: 'メニュー順 編集' }, 選択メニュー.map((mid, i) => h('li', {},
        h('span', { class: '伸びる' }, メニュー対応[mid]?.name || '(削除されたメニュー)', h('small', {}, ` ${メニュー対応[mid]?.minutes || 0}分`)),
        h('button', { type: 'button', class: 'アイコンボタン', 'aria-label': '上へ', disabled: i === 0, onclick: () => { [選択メニュー[i - 1], 選択メニュー[i]] = [選択メニュー[i], 選択メニュー[i - 1]]; メニュー欄を更新(); } }, '↑'),
        h('button', { type: 'button', class: 'アイコンボタン', 'aria-label': '下へ', disabled: i === 選択メニュー.length - 1, onclick: () => { [選択メニュー[i + 1], 選択メニュー[i]] = [選択メニュー[i], 選択メニュー[i + 1]]; メニュー欄を更新(); } }, '↓'),
        h('button', { type: 'button', class: 'アイコンボタン', 'aria-label': '外す', onclick: () => { 選択メニュー.splice(i, 1); メニュー欄を更新(); } }, '×')))) : h('p', { class: '空 小' }, 'まだメニューがありません'),
      h('button', {
        type: 'button', class: 'ボタン 控えめ',
        onclick: async () => {
          const 追加 = await シート('メニューを追加', (閉じる) => {
            const 検索 = h('input', { type: 'search', placeholder: '名前・分類で絞り込み' });
            const 一覧 = h('div', { class: 'リスト' });
            const 絞り込み = () => {
              const q = 検索.value.trim();
              置き換え(一覧, ...メニュー.filter((m) => !q || `${m.name}${m.category}${m.purpose}`.includes(q)).map((m) => h('button', { type: 'button', class: 'リスト項目', onclick: () => 閉じる(m.id) },
                h('div', { class: '伸びる' }, h('strong', {}, m.name), h('small', {}, [m.category, `${m.minutes}分`, m.purpose].filter(Boolean).join(' ・ '))),
                h('span', { class: '追加' }, '＋'))));
            };
            検索.addEventListener('input', 絞り込み);
            絞り込み();
            return [検索, 一覧, h('a', { class: '小リンク', href: '#/menus' }, 'メニューのテンプレートを編集する')];
          });
          if (追加) { 選択メニュー.push(追加); メニュー欄を更新(); }
        },
      }, '＋ メニューを追加'));
  };
  メニュー欄を更新();

  const 値 = 既存 || { kind: '練習', date: 指定日 || 今日の日付(), start_time: '16:00', end_time: '18:30', place: '体育館', published: 1 };
  const フォーム要素 = フォーム([
    { 名前: 'kind', ラベル: '種類', 種類: 'select', 選択肢: ['練習', '試合', 'その他'] },
    { 名前: 'title', ラベル: 'タイトル', 例: '例：通常練習／練習試合 vs 〇〇高' },
    { 名前: 'date', ラベル: '日付', 種類: 'date', 必須: true },
    { 名前: 'start_time', ラベル: '開始', 種類: 'time' },
    { 名前: 'end_time', ラベル: '終了', 種類: 'time' },
    { 名前: 'place', ラベル: '場所' },
    { 名前: 'notes', ラベル: 'メモ・持ち物', 種類: 'textarea' },
    { 名前: 'published', ラベル: '選手に公開する（オフにすると下書き）', 種類: 'checkbox' },
  ], async (入力) => {
    const 本文 = { ...入力, menu_ids: 選択メニュー };
    const 結果 = id ? await api('PUT', `/api/events/${id}`, 本文) : await api('POST', '/api/events', 本文);
    通知('保存しました');
    location.hash = `#/events/${結果.id}`;
  }, { 値: { ...値, published: Boolean(値.published) } });
  フォーム要素.insertBefore(メニュー欄, フォーム要素.querySelector('button[type=submit]'));

  描画(見出し(id ? '予定を編集' : '予定を追加', null, id ? `#/events/${id}` : '#/schedule'), h('div', { class: 'カード' }, フォーム要素));
}

export async function 練習履歴画面() {
  const メニュー = await api('GET', '/api/menus');
  const 結果欄 = h('div', {});
  const 検索する = async (条件) => {
    const q = new URLSearchParams({ order: 'desc', to: 条件.to || 今日の日付() });
    if (条件.q) q.set('q', 条件.q);
    if (条件.from) q.set('from', 条件.from);
    if (条件.kind) q.set('kind', 条件.kind);
    if (条件.menu_id) q.set('menu_id', 条件.menu_id);
    const 予定 = await api('GET', `/api/events?${q}`);
    const 合計分 = 予定.reduce((a, e) => a + (e.total_minutes || 0), 0);
    置き換え(結果欄, 
      オフライン注記(予定) || '',
      h('p', { class: '件数' }, `${予定.length}件 ・ メニュー合計 ${Math.floor(合計分 / 60)}時間${合計分 % 60}分`),
      予定.length ? h('div', { class: 'リスト カード' }, 予定.map((e) => h('a', { class: 'リスト項目', href: `#/events/${e.id}` },
        h('div', { class: '日付箱' }, 日付表示(e.date)),
        h('div', { class: '伸びる' },
          h('strong', {}, e.title),
          h('small', {}, e.menus.map((m) => m.name).join('・') || 'メニュー未登録')),
        h('small', { class: '数' }, `${e.attend_count}人`)))) : 空表示('条件に合う練習はありません'));
  };
  const 三か月前 = new Date();
  三か月前.setMonth(三か月前.getMonth() - 3);
  const 指定メニュー = new URLSearchParams(location.hash.split('?')[1] || '').get('menu') || '';
  const 初期 = 指定メニュー
    ? { menu_id: 指定メニュー, from: '', to: 今日の日付() }
    : { kind: '練習', from: 日付文字列(三か月前), to: 今日の日付() };
  描画(
    見出し('練習履歴', null, '#/more'),
    h('details', { class: 'カード', open: true },
      h('summary', {}, '🔎 検索条件'),
      フォーム([
        { 名前: 'q', ラベル: 'キーワード（タイトル・メモ・メニュー名）', 種類: 'search' },
        { 名前: 'menu_id', ラベル: '使ったメニュー', 種類: 'select', 選択肢: [['', 'すべて'], ...メニュー.map((m) => [m.id, m.name])] },
        { 名前: 'kind', ラベル: '種類', 種類: 'select', 選択肢: [['', 'すべて'], '練習', '試合', 'その他'] },
        { 名前: 'from', ラベル: 'いつから', 種類: 'date' },
        { 名前: 'to', ラベル: 'いつまで', 種類: 'date' },
      ], 検索する, { 送信文言: '検索', 値: 初期 })),
    結果欄);
  await 検索する(初期);
}
