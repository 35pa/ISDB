// ウェブ版（お試し版）の起動処理：Pyodide（ブラウザで動く Python）でサーバーの API をそのまま動かす。
// アプリ本体（公開/*.js）は api() から globalThis.お試し版.fetch を呼ぶので、サーバーなしで全機能が動く。
// データは端末の IndexedDB に保存する（ほかの端末とは共有しない）。

(() => {
  const デモ = { チームコード: 'DEMO22', パスワード: 'demo-pass1' };
  const 起動画面 = document.getElementById('起動画面');
  const 状況 = document.getElementById('起動状況');
  const 表示 = (文言) => { if (状況) 状況.textContent = 文言; };

  // ---- 端末への保存（IndexedDB）。使えない環境ではメモリ上だけで動かす ----
  const 保存庫を開く = () => new Promise((解決) => {
    try {
      const 要求 = indexedDB.open('バスケ部ノート', 1);
      要求.onupgradeneeded = () => 要求.result.createObjectStore('データ');
      要求.onsuccess = () => 解決(要求.result);
      要求.onerror = () => 解決(null);
    } catch { 解決(null); }
  });
  const 保存庫 = 保存庫を開く();
  const 操作 = async (種類, 処理) => {
    const db = await 保存庫;
    if (!db) return null;
    return new Promise((解決) => {
      try {
        const 要求 = 処理(db.transaction('データ', 種類).objectStore('データ'));
        要求.onsuccess = () => 解決(要求.result ?? null);
        要求.onerror = () => 解決(null);
      } catch { 解決(null); }
    });
  };
  const 読む = () => 操作('readonly', (s) => s.get('db'));
  const 書く = (値) => 操作('readwrite', (s) => s.put(値, 'db'));
  const 消す = () => 操作('readwrite', (s) => s.delete('db'));

  // 公開先には圧縮ファイル（.zip・.whl）を置けないので、Base64 の文字にした「〜.txt」を読み、元のバイト列に戻して渡す
  const 元のfetch = globalThis.fetch.bind(globalThis);
  globalThis.fetch = async (入力, 設定) => {
    const URL文字列 = typeof 入力 === 'string' ? 入力 : 入力 instanceof URL ? 入力.href : 入力?.url;
    if (URL文字列 && /\.(zip|whl)$/.test(new URL(URL文字列, location.href).pathname)) {
      // Pyodide が付ける integrity（元のファイルのハッシュ）は文字にしたファイルとは合わないので付けない
      const 応答 = await 元のfetch(`${URL文字列}.txt`);
      if (!応答.ok) return 応答;
      const 文字 = atob((await 応答.text()).trim());
      const 中身 = new Uint8Array(文字.length);
      for (let i = 0; i < 文字.length; i++) 中身[i] = 文字.charCodeAt(i);
      return new Response(中身, { status: 200, headers: { 'Content-Type': 'application/octet-stream' } });
    }
    return 元のfetch(入力, 設定);
  };

  let 本体 = null; // Python の「ブラウザ版」モジュール
  const 準備 = (async () => {
    if (typeof WebAssembly !== 'object') throw new Error('このブラウザは WebAssembly に対応していません');
    表示('アプリを読み込んでいます（初回は数十秒かかります）');
    const pyodide = await loadPyodide({ indexURL: new URL('pyodide/', location.href).href, stdout: () => {}, stderr: (t) => console.warn(t) });
    表示('データベースを準備しています');
    await pyodide.loadPackage(['sqlite3', 'hashlib'], { messageCallback: () => {} });
    const 圧縮 = await fetch('アプリ.zip');
    if (!圧縮.ok) throw new Error('アプリのファイルを読み込めませんでした');
    pyodide.unpackArchive(await 圧縮.arrayBuffer(), 'zip', { extractDir: '/アプリ' });
    pyodide.runPython("import sys; sys.path.insert(0, '/アプリ')");
    本体 = pyodide.pyimport('ブラウザ版');
    const 保存 = await 読む();
    表示(保存 ? '保存したデータを読み込んでいます' : 'サンプルデータを作っています');
    本体.開始(保存 || null);
    if (!保存) await 保存する();
  })();

  async function 保存する() {
    const 中身 = 本体.中身();
    try { await 書く(中身.toJs()); } finally { 中身.destroy(); }
  }
  let 保存待ち = null;
  const 保存予約 = () => { clearTimeout(保存待ち); 保存待ち = setTimeout(保存する, 300); };
  document.addEventListener('visibilitychange', () => { if (document.hidden && 保存待ち) { clearTimeout(保存待ち); 保存待ち = null; 保存する(); } });

  準備.then(() => { 起動画面?.remove(); }).catch((エラー) => {
    console.error(エラー);
    表示(`この環境ではアプリを起動できませんでした（${エラー.message || エラー}）。Safari や Chrome の最新版で開き直してください。`);
    起動画面?.classList.add('失敗');
  });

  globalThis.お試し版 = {
    デモ,
    async fetch(パス, 設定 = {}) {
      await 準備;
      const メソッド = (設定.method || 'GET').toUpperCase();
      const 認可 = 設定.headers?.Authorization || '';
      const 結果 = JSON.parse(本体.API実行(メソッド, String(パス), 設定.body || '', 認可.startsWith('Bearer ') ? 認可.slice(7) : ''));
      if (メソッド !== 'GET' && 結果.status === 200) 保存予約();
      return new Response(JSON.stringify(結果.body), { status: 結果.status, headers: { 'Content-Type': 'application/json' } });
    },
    async 初期化() {
      await 準備;
      await 消す();
      本体.開始(null);
      await 保存する();
      location.hash = '#/login';
    },
  };
})();
