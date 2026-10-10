const CACHE_NAME = 'travelog-v2'; // ← バージョンを v2 に上げてキャッシュを強制更新させます
const urlsToCache = [
  '/',
  '/static/manifest.json'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(urlsToCache);
    })
  );
});

// 古いキャッシュを掃除する処理（あると安全です）
self.addEventListener('activate', (event) => {
  event.addEventListener('activate', event => {
    event.waitUntil(
      caches.keys().then(keys => Promise.all(
        keys.map(key => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      ))
    );
  });
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