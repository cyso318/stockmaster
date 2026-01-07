# StockMaster - Projektstruktur

## 📁 Hauptverzeichnis

```
inventory-app/
├── app.py                          # Haupt-Flask-Anwendung
├── auto_backup.py                  # Automatisches Backup-System
├── email_service.py                # E-Mail-Benachrichtigungen
├── notification_service.py         # Benachrichtigungssystem
├── generate_cert.py                # SSL-Zertifikat-Generator
├── requirements.txt                # Python-Abhängigkeiten
├── inventory.db                    # SQLite-Datenbank
│
├── static/                         # Statische Dateien
│   ├── app.js                      # Haupt-JavaScript
│   ├── quagga-scanner.js          # Barcode-Scanner
│   ├── label_designer.js          # Label-Designer
│   ├── manifest.json              # PWA-Manifest
│   ├── sw.js                      # Service Worker
│   └── uploads/                   # Hochgeladene Bilder
│
├── templates/                      # HTML-Templates
│   ├── index.html                 # Hauptanwendung
│   ├── login.html                 # Login-Seite
│   ├── register.html              # Registrierung
│   ├── profile.html               # Benutzerprofil
│   ├── users.html                 # Benutzerverwaltung
│   ├── label_designer.html        # Label-Designer
│   ├── print_barcodes.html        # Barcode-Druck
│   ├── offline.html               # Offline-Seite
│   ├── landing.html               # Landing Page
│   ├── impressum.html             # Impressum
│   ├── datenschutz.html           # Datenschutz
│   └── agb.html                   # AGB
│
├── backups/                        # Automatische Backups
│
├── venv/                           # Python Virtual Environment
│
└── Dokumentation/
    ├── README.md                   # Projekt-Übersicht
    ├── QUICKSTART.md              # Schnellstart-Anleitung
    ├── SECURITY.md                # Sicherheitshinweise
    ├── INSTALL_WINDOWS.md         # Windows-Installation
    ├── README_SECURITY_SETUP.md   # Sicherheitseinrichtung
    ├── AUTO_BACKUP_GUIDE.md       # Backup-Anleitung
    ├── DEPLOYMENT_GUIDE.md        # Deployment-Anleitung
    ├── PYTHONANYWHERE_SETUP.md    # PythonAnywhere Setup
    ├── PYTHONANYWHERE_QUICKSTART.txt
    ├── HTTP_vs_HTTPS.txt          # HTTP/HTTPS Info
    ├── HANDY_SETUP.txt            # Mobile Setup
    ├── https_aktivieren.bat       # HTTPS aktivieren
    ├── https_deaktivieren.bat     # HTTPS deaktivieren
    ├── firewall_regel_hinzufuegen.bat
    ├── start.bat                  # Windows Start-Script
    └── start.sh                   # Linux/Mac Start-Script
```

## 🔧 Konfigurationsdateien

- **`.env`** - Umgebungsvariablen (NICHT committen!)
- **`.env.example`** - Beispiel-Konfiguration
- **`.gitignore`** - Git-Ignore-Regeln
- **`requirements.txt`** - Python-Abhängigkeiten
- **`cert.pem / key.pem`** - SSL-Zertifikate (optional)

## 📊 Datenbank

**`inventory.db`** - SQLite-Datenbank mit folgenden Tabellen:

- `organizations` - Organisationen/Mandanten
- `users` - Benutzer
- `categories` - Artikelkategorien
- `locations` - Lagerorte
- `items` - Artikel
- `movements` - Bestandsbewegungen

## 🚀 Wichtige Dateien

### Backend (Python/Flask)
- **`app.py`** (99 KB) - Hauptanwendung mit allen Routes und Business Logic
- **`email_service.py`** - SMTP-E-Mail-Service für Benachrichtigungen
- **`notification_service.py`** - Automatische Benachrichtigungen bei niedrigem Bestand
- **`auto_backup.py`** - Automatisches Backup-System

### Frontend (JavaScript)
- **`static/app.js`** (47 KB) - Hauptlogik der Single-Page-Application
- **`static/quagga-scanner.js`** - Barcode-Scanner mit QuaggaJS
- **`static/label_designer.js`** - Label-Designer für Etiketten

### Templates
- **`templates/index.html`** (98 KB) - Hauptanwendung mit gesamtem UI
- **`templates/print_barcodes.html`** - Professioneller Barcode-Druck

## 🎨 Features

✅ Multi-Mandanten-System
✅ Benutzerverwaltung mit Rollen
✅ Artikelverwaltung mit Bildern
✅ Barcode-Scanner (Kamera + manuell)
✅ Barcode-Generierung und -Druck
✅ Label-Designer
✅ Bestandsbewegungen
✅ Wartungsverwaltung
✅ E-Mail-Benachrichtigungen
✅ Automatisches Backup
✅ PWA-fähig (Progressive Web App)
✅ Mobile-optimiert
✅ Dark Mode
✅ HTTPS-Support

## 📝 Entwicklung

### Server starten:
```bash
python app.py
```

### Zugriff:
- HTTP: `http://localhost:5000`
- HTTPS: `https://localhost:5000` (nach Zertifikat-Generierung)

### HTTPS aktivieren:
```bash
python generate_cert.py
# oder
https_aktivieren.bat
```

## 🔐 Sicherheit

- CSRF-Schutz aktiviert
- Session-basierte Authentifizierung
- Passwort-Hashing mit Werkzeug
- SQL-Injection-Schutz durch Prepared Statements
- HTTPS-Support für sichere Verbindungen

## 📦 Deployment

Siehe **DEPLOYMENT_GUIDE.md** für verschiedene Deployment-Optionen:
- PythonAnywhere (kostenlos)
- Render.com
- Heroku
- Google Cloud Run
- VPS (Hetzner, DigitalOcean, etc.)
