// ホーム：未読のお知らせ・直近の予定（出欠）・目標・次のステップ練習

import { api, h, 描画, 見出し, コーチか, 日付表示, 日時表示, 残り日数, バッジ, 出欠の色, 空表示, オフライン注記 } from './共通.js';
import { 進捗バー } from './図表.js';

export async function ホーム画面() {
  const データ = await api('GET', '/api/home');
  const 名前 = データ.user.name;
  描画(
    見出し(データ.team.name),
    オフライン注記(データ),
    h('p', { class: 'あいさつ' }, `${名前} さん、おつかれさまです`),

    データ.unread_notices.length ? h('section', { class: 'カード 強調枠' },
      h('h2', {}, `📣 未読のお知らせ（${データ.unread_notices.length}）`),
      h('div', { class: 'リスト' }, データ.unread_notices.slice(0, 3).map((p) => h('a', { class: 'リスト項目', href: `#/board/${p.id}` },
        h('span', { class: '未読点', 'aria-label': '未読' }),
        h('div', { class: '伸びる' }, h('strong', {}, p.title), h('small', {}, 日時表示(p.created_at))),
        h('span', { class: '矢印' }, '›'))))) : null,

    h('section', { class: 'カード' },
      h('div', { class: '行 間' }, h('h2', {}, '📅 これからの予定'), h('a', { href: '#/schedule', class: '小リンク' }, 'すべて')),
      データ.upcoming.length ? h('div', { class: 'リスト' }, データ.upcoming.map((e) => h('a', { class: 'リスト項目', href: `#/events/${e.id}` },
        h('div', { class: `日付箱 ${e.kind === '試合' ? '試合' : ''}` }, 日付表示(e.date)),
        h('div', { class: '伸びる' },
          h('strong', {}, e.title, e.published ? null : バッジ('下書き', '薄')),
          h('small', {}, [e.start_time && `${e.start_time}〜${e.end_time}`, e.place].filter(Boolean).join(' ・ ')),
          コーチか() ? h('small', {}, `出席 ${e.attend_count}人 ／ 回答 ${e.answered_count}/${データ.member_count}人`) : null),
        コーチか() ? null : (e.my_status ? バッジ(e.my_status, 出欠の色[e.my_status]) : バッジ('未回答', '強調'))))) : 空表示('2週間以内の予定はありません')),

    !コーチか() && データ.steps?.length ? h('section', { class: 'カード' },
      h('div', { class: '行 間' }, h('h2', {}, '🪜 次に取り組む練習'), h('a', { href: '#/skills', class: '小リンク' }, 'スキル診断')),
      h('div', { class: 'リスト' }, データ.steps.map((r) => h('a', { class: 'リスト項目', href: '#/skills' },
        h('div', { class: '伸びる' },
          h('small', {}, `${r.category_name}・${r.drill.level} ステップ${r.drill.order}`, r.overridden ? ' ・ コーチ指定' : ''),
          h('strong', {}, r.drill.title),
          進捗バー(r.completed, r.total)),
        r.priority ? バッジ(`優先${r.priority}`, '強調') : null)))) : null,

    !コーチか() && データ.unconfirmed_feedback ? h('a', { class: 'カード 強調枠 リンクカード', href: '#/karte' },
      `💬 コーチからのフィードバックが ${データ.unconfirmed_feedback} 件あります`) : null,

    コーチか() && データ.step_reports?.length ? h('section', { class: 'カード' },
      h('div', { class: '行 間' }, h('h2', {}, '🪜 選手のステップ報告'), h('a', { href: '#/steps-overview', class: '小リンク' }, '一覧')),
      h('div', { class: 'リスト' }, データ.step_reports.map((r) => h('a', { class: 'リスト項目', href: `#/skills/${r.player_id}` },
        h('div', { class: '伸びる' },
          h('strong', {}, `${r.player_name}：${r.title}`),
          h('small', {}, `${日付表示(r.date)} ・ 自己評価 ${'★'.repeat(r.self_rating)}${r.comment ? ` ・ ${r.comment}` : ''}`)),
        r.cleared ? バッジ('クリア', '良') : バッジ('継続', '薄'))))) : null,

    h('section', { class: 'カード' },
      h('div', { class: '行 間' }, h('h2', {}, '🎯 目標'), h('a', { href: '#/goals', class: '小リンク' }, '管理')),
      データ.goals.length ? h('div', { class: 'リスト' }, データ.goals.map((g) => {
        const 残り = 残り日数(g.deadline);
        return h('a', { class: 'リスト項目 縦', href: '#/goals' },
          h('div', { class: '行 間' },
            h('strong', {}, `${g.scope === 'チーム' ? '👥 ' : ''}${g.content}`),
            残り === null ? null : バッジ(残り >= 0 ? `あと${残り}日` : '期限切れ', 残り < 7 ? '注意' : '薄')),
          進捗バー(g.progress));
      })) : 空表示('進行中の目標はありません')),
  );
}
