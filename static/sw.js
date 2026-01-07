// Service Worker für StockMaster PWA
// Ermöglicht Offline-Funktionalität und schnelleres Laden

const CACHE_VERSION = 'stockmaster-v1.0.0';
const CACHE_NAME = `${CACHE_VERSION}-static`;
const DATA_CACHE_NAME = `${CACHE_VERSION}-data`;

// Dateien, die beim Install gecacht werden (kritische Dateien)
const STATIC_CACHE_URLS = [
    '/',
    '/static/app.js',
    '/static/manifest.json',
    '/offline',  // Offline-Fallback-Seite
];

// Installationsevent - Cachen der statischen Ressourcen
self.addEventListener('install', (event) => {
    console.log('[SW] Service Worker wird installiert...', CACHE_VERSION);

    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('[SW] Cache geöffnet, füge statische Dateien hinzu');
                return cache.addAll(STATIC_CACHE_URLS);
            })
            .then(() => {
                console.log('[SW] Installation abgeschlossen');
                return self.skipWaiting();  // Aktiviere sofort
            })
            .catch((error) => {
                console.error('[SW] Fehler beim Cachen:', error);
            })
    );
});

// Aktivierungsevent - Aufräumen alter Caches
self.addEventListener('activate', (event) => {
    console.log('[SW] Service Worker wird aktiviert...', CACHE_VERSION);

    event.waitUntil(
        caches.keys()
            .then((cacheNames) => {
                return Promise.all(
                    cacheNames
                        .filter((cacheName) => {
                            // Lösche alle Caches außer dem aktuellen
                            return cacheName.startsWith('stockmaster-') &&
                                   cacheName !== CACHE_NAME &&
                                   cacheName !== DATA_CACHE_NAME;
                        })
                        .map((cacheName) => {
                            console.log('[SW] Lösche alten Cache:', cacheName);
                            return caches.delete(cacheName);
                        })
                );
            })
            .then(() => {
                console.log('[SW] Aktivierung abgeschlossen');
                return self.clients.claim();  // Übernehme alle Clients sofort
            })
    );
});

// Fetch-Event - Netzwerk-Requests abfangen
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Nur für same-origin Requests
    if (url.origin !== location.origin) {
        return;
    }

    // API-Requests - Network First mit Cache-Fallback
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(request)
                .then((response) => {
                    // Klone Response für Cache
                    const responseClone = response.clone();

                    // Speichere erfolgreiche GET-Requests im Data-Cache
                    if (request.method === 'GET' && response.status === 200) {
                        caches.open(DATA_CACHE_NAME)
                            .then((cache) => {
                                cache.put(request, responseClone);
                            });
                    }

                    return response;
                })
                .catch(() => {
                    // Bei Netzwerkfehler: Versuche aus Cache
                    return caches.match(request)
                        .then((cachedResponse) => {
                            if (cachedResponse) {
                                console.log('[SW] API aus Cache geladen:', url.pathname);
                                return cachedResponse;
                            }

                            // Wenn nichts im Cache: Gebe Offline-Response zurück
                            return new Response(
                                JSON.stringify({
                                    error: 'Offline',
                                    message: 'Keine Internetverbindung verfügbar'
                                }),
                                {
                                    status: 503,
                                    headers: { 'Content-Type': 'application/json' }
                                }
                            );
                        });
                })
        );
        return;
    }

    // Statische Ressourcen - Cache First mit Network-Fallback
    event.respondWith(
        caches.match(request)
            .then((cachedResponse) => {
                if (cachedResponse) {
                    // Im Cache gefunden - gebe zurück und update im Hintergrund
                    fetch(request)
                        .then((response) => {
                            if (response.status === 200) {
                                caches.open(CACHE_NAME)
                                    .then((cache) => {
                                        cache.put(request, response);
                                    });
                            }
                        })
                        .catch(() => {
                            // Netzwerkfehler beim Update ignorieren
                        });

                    return cachedResponse;
                }

                // Nicht im Cache - hole aus Netzwerk
                return fetch(request)
                    .then((response) => {
                        // Klone für Cache
                        const responseClone = response.clone();

                        // Cache nur erfolgreiche Responses
                        if (response.status === 200) {
                            caches.open(CACHE_NAME)
                                .then((cache) => {
                                    cache.put(request, responseClone);
                                });
                        }

                        return response;
                    })
                    .catch(() => {
                        // Bei HTML-Requests: Zeige Offline-Seite
                        if (request.headers.get('accept').includes('text/html')) {
                            return caches.match('/offline');
                        }

                        // Für andere Ressourcen: Fehler-Response
                        return new Response('Offline - Ressource nicht verfügbar', {
                            status: 503,
                            statusText: 'Service Unavailable'
                        });
                    });
            })
    );
});

// Background Sync - Für Offline-Aktionen
self.addEventListener('sync', (event) => {
    console.log('[SW] Background Sync Event:', event.tag);

    if (event.tag === 'sync-items') {
        event.waitUntil(
            syncOfflineChanges()
        );
    }
});

async function syncOfflineChanges() {
    console.log('[SW] Synchronisiere Offline-Änderungen...');

    try {
        // Hole Offline-Änderungen aus IndexedDB (wenn implementiert)
        // und sende sie an den Server

        // Beispiel:
        // const changes = await getOfflineChanges();
        // for (const change of changes) {
        //     await fetch('/api/items', {
        //         method: change.method,
        //         body: JSON.stringify(change.data)
        //     });
        // }

        console.log('[SW] Synchronisierung abgeschlossen');
        return Promise.resolve();

    } catch (error) {
        console.error('[SW] Fehler bei Synchronisierung:', error);
        return Promise.reject(error);
    }
}

// Push-Benachrichtigungen (für zukünftige Implementierung)
self.addEventListener('push', (event) => {
    console.log('[SW] Push-Benachrichtigung empfangen');

    const data = event.data ? event.data.json() : {};

    const options = {
        body: data.body || 'Neue Benachrichtigung von StockMaster',
        icon: '/static/icons/icon-192x192.png',
        badge: '/static/icons/icon-72x72.png',
        vibrate: [200, 100, 200],
        data: {
            url: data.url || '/'
        },
        actions: [
            {
                action: 'open',
                title: 'Öffnen'
            },
            {
                action: 'close',
                title: 'Schließen'
            }
        ]
    };

    event.waitUntil(
        self.registration.showNotification(
            data.title || 'StockMaster',
            options
        )
    );
});

// Notification Click Handler
self.addEventListener('notificationclick', (event) => {
    console.log('[SW] Benachrichtigung geklickt:', event.action);

    event.notification.close();

    if (event.action === 'open' || !event.action) {
        const url = event.notification.data.url || '/';

        event.waitUntil(
            clients.matchAll({ type: 'window', includeUncontrolled: true })
                .then((clientList) => {
                    // Fokussiere existierendes Fenster wenn vorhanden
                    for (const client of clientList) {
                        if (client.url === url && 'focus' in client) {
                            return client.focus();
                        }
                    }

                    // Öffne neues Fenster
                    if (clients.openWindow) {
                        return clients.openWindow(url);
                    }
                })
        );
    }
});

// Nachricht vom Client (für manuelles Cache-Update)
self.addEventListener('message', (event) => {
    console.log('[SW] Nachricht empfangen:', event.data);

    if (event.data.action === 'skipWaiting') {
        self.skipWaiting();
    }

    if (event.data.action === 'clearCache') {
        event.waitUntil(
            caches.keys()
                .then((cacheNames) => {
                    return Promise.all(
                        cacheNames.map((cacheName) => {
                            return caches.delete(cacheName);
                        })
                    );
                })
                .then(() => {
                    event.ports[0].postMessage({ success: true });
                })
        );
    }
});

console.log('[SW] Service Worker geladen', CACHE_VERSION);
