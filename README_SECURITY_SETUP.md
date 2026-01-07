# StockMaster - Sicherheits-Setup Anleitung

## Schnellstart

### 1. Installation

```bash
# Abhängigkeiten installieren
pip install -r requirements.txt
```

### 2. Erstes Setup

Die Anwendung wurde mit umfangreichen Sicherheitsmaßnahmen ausgestattet:

```bash
# Anwendung starten
python app.py
```

Beim ersten Start:
- Datenbank wird automatisch erstellt
- Admin-Account wird angelegt:
  - **Benutzername**: `admin`
  - **Passwort**: `admin123`
  - **⚠️ WICHTIG**: Passwort sofort ändern!

### 3. Passwort ändern

1. Mit `admin` / `admin123` anmelden
2. Auf "Profil" klicken
3. Neues sicheres Passwort vergeben (mind. 6 Zeichen)

## Sicherheits-Features

### ✅ Was wurde implementiert:

1. **bcrypt Password Hashing** - Sichere Passwort-Speicherung
2. **CSRF-Schutz** - Schutz vor Cross-Site Request Forgery
3. **Rate Limiting** - Schutz vor Brute-Force-Angriffen
4. **Session-Sicherheit** - HTTPOnly, SameSite Cookies
5. **Input-Validierung** - Schutz vor ungültigen Eingaben
6. **SQL-Injection-Schutz** - Parametrisierte Queries
7. **Security Headers** - XSS, Clickjacking, MIME-Sniffing Schutz
8. **Sichere SECRET_KEY** - Zufällig generiert

## Konfiguration (.env-Datei)

Die `.env`-Datei enthält wichtige Sicherheitseinstellungen:

```bash
# Generieren Sie eine neue SECRET_KEY für Produktion:
python -c "import secrets; print(secrets.token_hex(32))"
```

### Wichtige Einstellungen:

| Variable | Entwicklung | Produktion |
|----------|-------------|------------|
| `DEBUG` | `True` | `False` |
| `SESSION_COOKIE_SECURE` | `False` | `True` (nur mit HTTPS!) |
| `SECRET_KEY` | generiert | **ÄNDERN!** |

## Entwicklung vs. Produktion

### Entwicklung (Aktuell)
```bash
# .env
DEBUG=True
SESSION_COOKIE_SECURE=False
HOST=127.0.0.1
PORT=5000
```

```bash
python app.py
```

Zugriff: http://127.0.0.1:5000

### Produktion (Empfohlen)

1. **HTTPS einrichten** (z.B. mit Let's Encrypt)
2. **.env anpassen**:
   ```bash
   DEBUG=False
   SESSION_COOKIE_SECURE=True
   SECRET_KEY=<neue-sichere-key>
   ```

3. **Reverse Proxy verwenden** (Nginx/Apache)
4. **Gunicorn als WSGI-Server**:
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 127.0.0.1:5000 app:app
   ```

## Rate Limiting

Die Anwendung schützt vor Brute-Force-Angriffen:

- **Login**: 5 Versuche pro Minute
- **API**: 100 Anfragen pro Minute

Anpassen in `.env`:
```bash
LOGIN_RATE_LIMIT=5 per minute
API_RATE_LIMIT=100 per minute
```

Für Produktion mit Redis (empfohlen):
```bash
# Redis installieren und starten
RATELIMIT_STORAGE_URL=redis://localhost:6379
```

## Sicherheits-Checkliste

### Vor Produktionsstart:

- [ ] Admin-Passwort geändert
- [ ] SECRET_KEY neu generiert
- [ ] SESSION_COOKIE_SECURE=True (nur mit HTTPS!)
- [ ] DEBUG=False
- [ ] HTTPS/SSL-Zertifikat konfiguriert
- [ ] Firewall-Regeln gesetzt
- [ ] Backup-Strategie implementiert
- [ ] `.env` in .gitignore
- [ ] Security Headers aktiviert (automatisch mit HTTPS)

### Regelmäßig:

- [ ] Passwörter aktualisieren
- [ ] Logs auf verdächtige Aktivitäten prüfen
- [ ] Abhängigkeiten aktualisieren (`pip list --outdated`)
- [ ] Backups testen

## Benutzer-Management

### Neuen Benutzer anlegen

1. Als Admin anmelden
2. "Benutzer" Button klicken
3. Neuen Benutzer erstellen
4. Admin-Rechte optional vergeben

### Passwort-Anforderungen

- Mindestens 6 Zeichen
- Empfohlen: Kombination aus Groß-/Kleinbuchstaben, Zahlen, Sonderzeichen

## Troubleshooting

### "Import konnte nicht aufgelöst werden" Fehler

```bash
# Alle Pakete installieren
pip install -r requirements.txt
```

### "CSRF token missing" Fehler

- Browser-Cache leeren
- Neu anmelden
- Sicherstellen, dass JavaScript aktiviert ist

### Session läuft zu schnell ab

In `.env`:
```bash
PERMANENT_SESSION_LIFETIME=86400  # 24 Stunden (in Sekunden)
```

### Rate Limit zu streng

In `.env`:
```bash
LOGIN_RATE_LIMIT=10 per minute  # Von 5 auf 10 erhöht
```

## Was als Nächstes?

### Optional hinzufügen:

1. **2-Faktor-Authentifizierung (2FA)**
2. **Email-Benachrichtigungen**
3. **Audit-Logging aller Admin-Aktionen**
4. **Automatische Backups**
5. **Passwort-Zurücksetzung per E-Mail**

## Detaillierte Sicherheitsdokumentation

Siehe: `SECURITY.md` für vollständige technische Details

## Datenschutz

- Passwörter werden **nie** im Klartext gespeichert
- bcrypt-Hashing mit automatischem Salting
- Sessions sind verschlüsselt
- Keine Daten werden an Dritte gesendet

## Lizenz & Haftung

Diese Anwendung wird "as-is" bereitgestellt. Für Produktionsumgebungen wird empfohlen:
- Professionelles Security-Audit durchzuführen
- Regelmäßige Sicherheitsupdates einzuspielen
- Backup- und Disaster-Recovery-Plan zu haben

---

**Viel Erfolg mit StockMaster! 🎉**

Bei Fragen oder Problemen: Issues im Repository erstellen.
