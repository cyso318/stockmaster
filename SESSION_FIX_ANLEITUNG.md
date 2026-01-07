# Fix: Login führt zurück zur Startseite

## Problem
Nach dem Login kommt man immer wieder auf der Landing Page raus, statt zum Dashboard zu gelangen.

## Ursache
Die Session-Cookies werden durch den Nginx Reverse-Proxy nicht korrekt weitergegeben.

---

## Lösung: Schnell-Fix auf dem Server

### Schritt 1: Dateien zum Server hochladen

Kopiere diese Datei auf den Server:
```bash
scp fix_session_problem.sh stockmaster@DEINE_IP:/home/stockmaster/
```

### Schritt 2: Auf dem Server einloggen

```bash
ssh stockmaster@DEINE_IP
```

### Schritt 3: Fix-Script ausführen

```bash
cd /home/stockmaster
chmod +x fix_session_problem.sh
./fix_session_problem.sh
```

Das Script wird:
1. ✅ Backup der Nginx-Config erstellen
2. ✅ Nginx-Config mit korrekten Cookie-Headern aktualisieren
3. ✅ Nginx testen
4. ✅ Services neu starten
5. ✅ Status prüfen

### Schritt 4: Testen

Öffne im Browser: `http://DEINE_IP/login`

Login: `admin` / `admin123`

→ Du solltest jetzt zum Dashboard weitergeleitet werden!

---

## Alternative: Manuelle Fix

Falls das Script nicht funktioniert:

### 1. Nginx-Config bearbeiten

```bash
sudo nano /etc/nginx/sites-available/stockmaster
```

### 2. Diese Zeilen hinzufügen

Im `location /` Block, nach `proxy_set_header X-Forwarded-Proto $scheme;`:

```nginx
proxy_set_header X-Forwarded-Host $host;
proxy_set_header X-Forwarded-Port $server_port;

# WICHTIG für Sessions:
proxy_set_header Cookie $http_cookie;
proxy_pass_header Set-Cookie;
```

### 3. Speichern und Services neu starten

```bash
sudo nginx -t  # Test
sudo systemctl restart nginx
sudo systemctl restart stockmaster
```

---

## Debug: Session-Status prüfen

Öffne: `http://DEINE_IP/debug-session`

Diese Seite zeigt:
- Session-Konfiguration
- Aktuelle Session-Daten
- Cookie-Informationen
- Test-Login-Button

Wenn unter "4. Cookies" kein Cookie namens `session` erscheint, funktionieren die Cookies nicht.

---

## Falls es immer noch nicht funktioniert

### 1. Logs prüfen

```bash
# Gunicorn Logs
tail -50 /home/stockmaster/stockmaster/logs/gunicorn-error.log

# Systemd Logs
sudo journalctl -u stockmaster -n 50

# Nginx Logs
sudo tail -50 /var/log/nginx/error.log
```

### 2. Prüfe .env Datei

```bash
cat /home/stockmaster/stockmaster/.env
```

Sollte enthalten:
```
SESSION_COOKIE_HTTPONLY=False
SESSION_COOKIE_SAMESITE=None
SESSION_COOKIE_SECURE=False
```

### 3. Browser-Cache leeren

- Drücke `Ctrl+Shift+Delete`
- Lösche Cookies für deine IP
- Oder teste im Inkognito-Modus

### 4. SECRET_KEY konsistent?

```bash
# Prüfe ob SECRET_KEY in .env gesetzt ist:
grep SECRET_KEY /home/stockmaster/stockmaster/.env
```

Muss einen festen Wert haben (nicht leer)!

---

## Was wurde geändert?

### app.py
- ✅ CSRF-Schutz von `/login` und `/api/register` entfernt
- ✅ `ProxyFix` Middleware hinzugefügt
- ✅ Session-Cookie-Einstellungen optimiert
- ✅ Debug-Route `/debug-session` hinzugefügt

### Nginx-Config
- ✅ `X-Forwarded-Host` und `X-Forwarded-Port` Header hinzugefügt
- ✅ `Cookie` Header durchreichen
- ✅ `Set-Cookie` Header durchreichen

### .env
- ✅ `SESSION_COOKIE_SAMESITE=None` (erlaubt IP-Zugriff)
- ✅ `SESSION_COOKIE_HTTPONLY=False` (für Debugging)
- ✅ `SESSION_COOKIE_SECURE=False` (für HTTP)

---

## Kontakt

Bei weiteren Problemen: r.weschenfelder@proton.me

**Stand:** Januar 2025
