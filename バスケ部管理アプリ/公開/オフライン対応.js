// サービスワーカー：アプリ本体をキャッシュし、電波がないときも練習メニュー・作戦図などを閲覧できるようにする

const 版 = 'v1';
const 本体キャッシュ = `本体-${版}`;
const APIキャッシュ = 'API結果';
const 本体ファイル = [
  './',
  './index.html',
  './スタイル.css',
  './manifest.webmanifest',
  './アイコン.svg',
  './アプリ.js',
  './共通.js',
  './図表.js',
  './画面_ホーム.js',
  './画面_予定.js',
  './画面_練習メニュー.js',
  './画面_作戦ボード.js',
  './画面_メンバー.js',
  './画面_選手カルテ.js',
  './画面_スキル.js',
  './画面_目標.js',
  './画面_掲示板.js',
  './画面_設定.js',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(本体キャッシュ).then((c) => c.addAll(本体ファイル)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((名前一覧) => Promise.all(名前一覧.filter((n) => n.startsWith('本体-') && n !== 本体キャッシュ).map((n) => caches.delete(n))))
      .then(() => self.clients.claim()),
  );
});

// ログアウト時に前のユーザーのデータを消す
self.addEventListener('message', (e) => {
  if (e.data === 'APIキャッシュ削除') e.waitUntil(caches.delete(APIキャッシュ));
});

async function API取得(request) {
  try {
    const 応答 = await fetch(request);
    if (応答.ok) {
      const 控え = 応答.clone();
      caches.open(APIキャッシュ).then((c) => c.put(request.url, 控え));
    }
    return 応答;
  } catch {
    const 保存 = await (await caches.open(APIキャッシュ)).match(request.url);
    if (!保存) {
      return new Response(JSON.stringify({ error: 'オフラインのため表示できません（一度オンラインで開いた画面は見られます）' }), {
        status: 503, headers: { 'Content-Type': 'application/json; charset=utf-8' },
      });
    }
    const 見出し = new Headers(保存.headers);
    見出し.set('X-Offline-Cache', '1');
    return new Response(await 保存.blob(), { status: 200, headers: 見出し });
  }
}

async function 本体取得(request) {
  const キャッシュ = await caches.open(本体キャッシュ);
  const 保存 = await キャッシュ.match(request, { ignoreSearch: true });
  const 最新 = fetch(request).then((応答) => {
    if (応答.ok) キャッシュ.put(request, 応答.clone());
    return 応答;
  }).catch(() => null);
  return 保存 || (await 最新) || (await キャッシュ.match('./index.html')) || new Response('オフラインです', { status: 503 });
}

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return;
  if (url.pathname.startsWith('/api/')) {
    e.respondWith(API取得(e.request));
    return;
  }
  e.respondWith(本体取得(e.request));
});
