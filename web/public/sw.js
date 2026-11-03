// Legacy worker retirement: do not cache app shell or assets.
// New app entry point unregisters this worker and clears previous shell caches.
self.addEventListener('install', event => {
  event.waitUntil(self.skipWaiting());
});
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key.startsWith('gold-terminal-')).map(key => caches.delete(key))))
      .then(() => self.registration.unregister())
      .then(() => self.clients.claim())
  );
});
