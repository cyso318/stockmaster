# StockMaster - Sicherheitsfeatures

## Übersicht

Dieses Dokument beschreibt alle implementierten Sicherheitsmaßnahmen in StockMaster.

---

## 🔒 Implementierte Sicherheitsfeatures

### 1. Session-Management

#### Session-Timeout
- **Automatischer Timeout nach 30 Minuten Inaktivität**
- Konfigurierbar über `SESSION_TIMEOUT_MINUTES` (Standard: 30)
- Bei "Angemeldet bleiben" wird Session permanent gesetzt

```python
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
```

#### Session-Cookies
- `HttpOnly` - Schutz vor JavaScript-Zugriff
- `SameSite=Lax` - CSRF-Schutz
- `Secure` - Optional für HTTPS (Production)

---

### 2. Passwort-Sicherheit

#### Verschlüsselung
- **bcrypt** - Industrie-Standard für Password-Hashing
- Individuelle Salts pro Passwort
- Automatische Kosten-Anpassung (12 Rounds)

#### Passwort-Policy
Neue Passwörter müssen erfüllen:
- ✅ Mindestens 8 Zeichen
- ✅ Mind. 1 Großbuchstabe
- ✅ Mind. 1 Kleinbuchstabe
- ✅ Mind. 1 Zahl

```python
def validate_password(password):
    # Prüft alle Anforderungen
    # Returns: (bool, message)
```

---

### 3. Account-Locking (Brute-Force-Schutz)

#### Automatische Sperrung
- **5 fehlgeschlagene Login-Versuche** → Account gesperrt
- **Sperrzeit: 15 Minuten**
- IP-basierte Sperrung
- Countdown der verbleibenden Versuche

```python
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)
```

#### Funktionsweise
1. Falsches Passwort → Zähler erhöhen
2. Bei 5 Fehlversuchen → `locked_until` setzen
3. Weitere Login-Versuche → Fehlermeldung mit Restzeit
4. Nach 15 Min → Automatische Entsperrung
5. Erfolgreicher Login → Zähler zurücksetzen

---

### 4. CSRF-Protection

#### Flask-WTF CSRF
- Automatischer Token-Generator
- Token-Validierung bei allen POST/PUT/DELETE Requests
- Custom Decorator `@csrf_protect_api()`

#### Token-Refresh
- Automatische Erneuerung alle 30 Minuten
- Erneuerung bei Seiten-Sichtbarkeit
- Automatischer Retry bei abgelaufenen Tokens

```javascript
// Frontend: Automatischer Token-Refresh
setInterval(refreshCSRFToken, 30 * 60 * 1000);
```

---

### 5. Rate Limiting

#### API Rate Limits
- **Login:** 5 Versuche pro Minute
- **API-Calls:** 100 Requests pro Minute
- IP-basierte Limitierung

```python
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=['100 per minute']
)

@app.route('/login')
@limiter.limit('5 per minute')
```

---

### 6. File Upload Security

#### Erlaubte Dateitypen
Nur Bilder erlaubt:
```python
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
```

#### Validierungen
- ✅ Dateityp-Prüfung (Extension)
- ✅ Dateigrößen-Limit: **5MB**
- ✅ Filename-Sanitization (secure_filename)
- ✅ Überschreiben alter Uploads

```python
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB
```

---

### 7. Security Headers

#### Development (HTTP)
```python
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
```

#### Production (HTTPS mit Talisman)
```python
Strict-Transport-Security: max-age=31536000
Content-Security-Policy:
  - default-src 'self'
  - script-src 'self' 'unsafe-inline' cdn.jsdelivr.net
  - style-src 'self' 'unsafe-inline'
  - img-src 'self' data:
  - frame-ancestors 'none'
```

---

### 8. SQL-Injection Schutz

#### Prepared Statements
Alle Datenbank-Queries verwenden Parameter-Binding:

```python
# ✅ SICHER
conn.execute('SELECT * FROM users WHERE username = ?', (username,))

# ❌ UNSICHER (wird nie verwendet)
conn.execute(f'SELECT * FROM users WHERE username = "{username}"')
```

---

### 9. Multi-Tenancy Isolation

#### Organisation-ID Filtering
- Jeder User gehört zu einer Organisation
- Alle Queries filtern nach `organization_id`
- Nutzer sehen nur ihre eigenen Daten

```python
@app.route('/api/items')
def get_items():
    organization_id = session.get('organization_id')
    items = conn.execute('''
        SELECT * FROM items
        WHERE organization_id = ?
    ''', (organization_id,))
```

---

## 🔧 Konfiguration

### Umgebungsvariablen (.env)

```bash
# Session
SECRET_KEY=<zufälliger-32-byte-hex>
SESSION_TIMEOUT_MINUTES=30
SESSION_COOKIE_SECURE=False  # True für Production/HTTPS

# Rate Limiting
LOGIN_RATE_LIMIT=5 per minute
API_RATE_LIMIT=100 per minute

# Security
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Lax
```

### Produktions-Empfehlungen

Für Production-Deployment:

```bash
# .env (Production)
SECRET_KEY=<starker-zufälliger-key>
SESSION_TIMEOUT_MINUTES=30
SESSION_COOKIE_SECURE=True  # HTTPS erforderlich!
DEBUG=False
```

---

## 🚨 Was NICHT implementiert ist

Diese Features sind **NICHT** vorhanden und müssten bei Bedarf ergänzt werden:

### Fehlt noch:
1. **2FA (Zwei-Faktor-Authentifizierung)** - TOTP/SMS
2. **Email-Verifikation** - Bei Registrierung
3. **Passwort-Reset** - "Passwort vergessen"-Funktion
4. **Audit-Logging** - Wer hat was geändert?
5. **IP-Whitelist** - Zugriffsbeschränkung auf bestimmte IPs
6. **Content Security** - Malware-Scanning bei Uploads
7. **Backup-Verschlüsselung** - Backups sind unverschlüsselt
8. **Database Encryption** - Datenbank ist unverschlüsselt
9. **Advanced Headers** - Subresource Integrity, Permission Policy

---

## 📊 Sicherheits-Checkliste

### Vor Production-Deployment

- [ ] `SECRET_KEY` auf starken Zufallswert setzen
- [ ] `SESSION_COOKIE_SECURE=True` aktivieren (HTTPS!)
- [ ] `DEBUG=False` setzen
- [ ] SSL-Zertifikat installieren (Let's Encrypt)
- [ ] Firewall konfigurieren (nur Port 80/443)
- [ ] Standard-Admin-Passwort ändern!
- [ ] Backup-Strategie einrichten
- [ ] Server-Updates aktivieren
- [ ] Fail2Ban installieren (optional)

### Regelmäßige Wartung

- [ ] Python-Packages aktualisieren (`pip list --outdated`)
- [ ] Server-Updates einspielen (`apt update && apt upgrade`)
- [ ] Logs prüfen (`/var/log/nginx/error.log`)
- [ ] Backups testen
- [ ] SSL-Zertifikat-Ablauf prüfen

---

## 🔍 Sicherheits-Tests

### Login-Tests

```bash
# Test Account-Locking
# 5x falsches Passwort eingeben
# → Sollte Account sperren

# Test Session-Timeout
# Login → 30 Min warten → Seite neu laden
# → Sollte zur Login-Seite weiterleiten
```

### File-Upload-Tests

```bash
# Test Dateityp-Validierung
# Versuche .exe, .php, .js hochzuladen
# → Sollte abgelehnt werden

# Test Dateigröße
# Versuche Datei > 5MB hochzuladen
# → Sollte abgelehnt werden
```

---

## 📞 Security Kontakt

Bei Sicherheitsproblemen oder Fragen:

**E-Mail:** r.weschenfelder@proton.me

Bitte verantwortungsvoll mit Sicherheitslücken umgehen (Responsible Disclosure).

---

## 📚 Ressourcen

### Security Best Practices
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Flask Security](https://flask.palletsprojects.com/en/2.3.x/security/)
- [DSGVO](https://dsgvo-gesetz.de/)

### Tools
- [bcrypt Calculator](https://bcrypt-generator.com/)
- [SSL Labs Test](https://www.ssllabs.com/ssltest/)
- [Security Headers Check](https://securityheaders.com/)

---

**Stand:** Januar 2025
**Version:** StockMaster 1.0
