const CACHE_NAME = 'travelog-v4'; // ← バージョンを v2 に上げてキャッシュを強制更新させます
const urlsToCache = [
  '/',
  '/static/manifest.json'
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.map(key => {
        if (key !== CACHE_NAME) {
          return caches.delete(key);
        }
      })
    ))
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // ★超重要：ページ遷移（HTMLの読み込み）やPOSTなどのリクエストは、
  // キャッシュを使わず、常に最新のネットワークデータを取得する
  if (event.request.mode === 'navigate' || event.request.method !== 'GET') {
    event.respondWith(fetch(event.request));
    return;
  }

  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});

self.addEventListener('fetch', (event) => {
  // ★超重要：GETリクエスト以外（POSTなど、写真アップロード）は
  // Service Workerを通さず、直接ネットワークに流す（iOSでのファイル消失を防ぐ）
  if (event.request.method !== 'GET') {
    event.respondWith(fetch(event.request));
    return;
  }

  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});