# 📦 Lagerverwaltungssystem mit Google Drive Sync

Eine moderne Web-Anwendung zur Verwaltung von Lagerbeständen mit automatischer Synchronisierung zu Google Drive.

## ✨ Features

- **Artikelverwaltung**: Artikel mit SKU, Beschreibung, Kategorie, Standort und mehr
- **Bestandsverwaltung**: Ein- und Ausbuchungen mit Historie
- **QR-Code-Generierung**: Automatische QR-Codes für jeden Artikel zum Drucken und Scannen
- **Kategorien & Standorte**: Flexible Organisation
- **Mindestbestand-Warnung**: Automatische Erkennung niedriger Bestände
- **Google Drive Backup**: Automatische Synchronisierung der Datenbank
- **CSV Export**: Datenexport für externe Nutzung
- **Responsive Design**: Funktioniert auf Desktop und Mobile
- **Echtzeit-Dashboard**: Übersicht über alle wichtigen Kennzahlen

## 🚀 Installation

### 1. Voraussetzungen

- Python 3.8 oder höher
- pip (Python Package Manager)
- Google Account für Drive-Integration

### 2. Projekt herunterladen

```bash
cd inventory-app
```

### 3. Virtuelle Umgebung erstellen (empfohlen)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 4. Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

## 🔧 Google Drive Setup

Um die Google Drive Synchronisierung zu nutzen, müssen Sie OAuth 2.0 Credentials erstellen:

### Schritt 1: Google Cloud Projekt erstellen

1. Gehen Sie zur [Google Cloud Console](https://console.cloud.google.com/)
2. Erstellen Sie ein neues Projekt oder wählen Sie ein bestehendes
3. Aktivieren Sie die **Google Drive API**:
   - Navigieren Sie zu "APIs & Services" > "Library"
   - Suchen Sie nach "Google Drive API"
   - Klicken Sie auf "Enable"

### Schritt 2: OAuth 2.0 Credentials erstellen

1. Gehen Sie zu "APIs & Services" > "Credentials"
2. Klicken Sie auf "Create Credentials" > "OAuth client ID"
3. Wählen Sie "Desktop app" als Application type
4. Geben Sie einen Namen ein (z.B. "Lagerverwaltung")
5. Klicken Sie auf "Create"
6. Laden Sie die JSON-Datei herunter
7. Benennen Sie die Datei in `credentials.json` um
8. Kopieren Sie sie in das Projektverzeichnis

### Schritt 3: Erste Authentifizierung

Beim ersten Sync werden Sie aufgefordert, sich mit Ihrem Google-Konto anzumelden:

```bash
python gdrive_sync.py
```

Dies öffnet automatisch Ihren Browser zur Authentifizierung.

## 🎯 Anwendung starten

```bash
python app.py
```

Die Anwendung ist dann verfügbar unter: **http://localhost:5000**

## 📖 Verwendung

### Dashboard

Das Dashboard zeigt Ihnen auf einen Blick:
- Gesamtanzahl der Artikel
- Anzahl der Kategorien und Standorte
- Artikel mit niedrigem Bestand
- Gesamtwert des Lagers

### Artikel verwalten

1. **Neuen Artikel anlegen**: Klicken Sie auf "+ Neuer Artikel"
2. **Artikel bearbeiten**: Klicken Sie bei einem Artikel auf "Bearbeiten"
3. **Artikel löschen**: Klicken Sie auf "Löschen" (mit Bestätigung)
4. **Suchen & Filtern**: Nutzen Sie die Suchleiste und Filter nach Kategorie/Standort

### Bestandsbuchungen

- **Einbuchen**: Erhöht den Bestand (z.B. bei Wareneingang)
- **Ausbuchen**: Verringert den Bestand (z.B. bei Verkauf/Verbrauch)
- Alle Bewegungen werden automatisch protokolliert

### Kategorien & Standorte

Organisieren Sie Ihre Artikel mit:
- **Kategorien**: z.B. Elektronik, Büromaterial, Werkzeuge
- **Standorte**: z.B. Lager A, Regal 1, Büro

### Google Drive Sync

- **Manueller Sync**: Klicken Sie auf "Sync zu Google Drive" im Header
- **Automatischer Sync**: Kann im Code konfiguriert werden
- Backups werden mit Zeitstempel in Google Drive gespeichert

### CSV Export

Exportieren Sie alle Artikel als CSV-Datei für:
- Externe Analysen
- Backup
- Import in andere Systeme

### QR-Codes

**Einzelner Artikel:**
- Klicken Sie bei einem Artikel auf "QR-Code"
- QR-Code wird angezeigt
- Herunterladen oder drucken

**Alle Artikel:**
- Klicken Sie auf "QR-Codes Drucken" im Header
- Wählen Sie die Größe (Normal, Klein, Groß)
- Drucken Sie auf Etiketten oder normales Papier

**Verwendung:**
- QR-Codes auf Artikel/Regale kleben
- Mit Smartphone scannen
- Direkt zum Artikel in der App

Siehe **QR_CODE_GUIDE.md** für detaillierte Anleitung!

## 🗂️ Datenbankstruktur

Die SQLite-Datenbank enthält folgende Tabellen:

- **items**: Haupttabelle für Artikel
- **categories**: Kategorien
- **locations**: Standorte
- **movements**: Bestandsbewegungen (Ein-/Ausbuchungen)
- **sync_log**: Protokoll der Google Drive Syncs

## 🔒 Sicherheit

- Die SQLite-Datenbank liegt lokal auf Ihrem Server
- Google Drive Credentials werden sicher in `token.pickle` gespeichert
- **Wichtig**: Fügen Sie `credentials.json` und `token.pickle` zu `.gitignore` hinzu!

### .gitignore Empfehlung

```
# Google Drive Credentials
credentials.json
token.pickle

# Datenbank
*.db
*.db-journal

# Backups
backups/

# Python
__pycache__/
*.pyc
venv/
.env
```

## ⚙️ Konfiguration

### Anpassungen in `app.py`

```python
# Server-Port ändern
app.run(debug=True, host='0.0.0.0', port=5000)

# Datenbank-Pfad
DB_PATH = 'inventory.db'

# Backup-Ordner
BACKUP_FOLDER = 'backups'
```

### Automatischer Sync

Um automatischen Sync zu aktivieren, fügen Sie in `app.py` hinzu:

```python
import threading
import time
from gdrive_sync import GoogleDriveSync

def auto_sync_worker():
    """Führt alle 30 Minuten einen Sync durch"""
    sync = GoogleDriveSync()
    sync.authenticate()
    sync.get_or_create_folder()
    
    while True:
        time.sleep(1800)  # 30 Minuten
        try:
            sync.upload_database()
            print("Auto-Sync erfolgreich")
        except Exception as e:
            print(f"Auto-Sync Fehler: {e}")

# In der main-Funktion starten
if __name__ == '__main__':
    init_db()
    
    # Auto-Sync im Hintergrund starten
    sync_thread = threading.Thread(target=auto_sync_worker, daemon=True)
    sync_thread.start()
    
    app.run(debug=True, host='0.0.0.0', port=5000)
```

## 🐛 Troubleshooting

### "Credentials Datei nicht gefunden"
- Stellen Sie sicher, dass `credentials.json` im Projektverzeichnis liegt
- Überprüfen Sie den Dateinamen (Groß-/Kleinschreibung beachten)

### "Port bereits in Verwendung"
- Ändern Sie den Port in `app.py`: `app.run(port=5001)`
- Oder beenden Sie die andere Anwendung auf Port 5000

### Google Drive Authentifizierung schlägt fehl
- Stellen Sie sicher, dass die Google Drive API aktiviert ist
- Überprüfen Sie, ob die credentials.json korrekt heruntergeladen wurde
- Löschen Sie `token.pickle` und authentifizieren Sie sich neu

## 📊 API-Endpunkte

Die Anwendung bietet folgende REST-API-Endpunkte:

### Dashboard
- `GET /api/dashboard` - Statistiken

### Kategorien
- `GET /api/categories` - Alle Kategorien
- `POST /api/categories` - Neue Kategorie
- `GET /api/categories/<id>` - Eine Kategorie
- `PUT /api/categories/<id>` - Kategorie aktualisieren
- `DELETE /api/categories/<id>` - Kategorie löschen

### Standorte
- `GET /api/locations` - Alle Standorte
- `POST /api/locations` - Neuer Standort
- `GET /api/locations/<id>` - Ein Standort
- `PUT /api/locations/<id>` - Standort aktualisieren
- `DELETE /api/locations/<id>` - Standort löschen

### Artikel
- `GET /api/items` - Alle Artikel (mit Filtern)
- `POST /api/items` - Neuer Artikel
- `GET /api/items/<id>` - Ein Artikel
- `PUT /api/items/<id>` - Artikel aktualisieren
- `DELETE /api/items/<id>` - Artikel löschen
- `POST /api/items/<id>/move` - Bestandsbewegung
- `GET /api/items/<id>/movements` - Bewegungshistorie

### Sync & Export
- `POST /api/sync/manual` - Manueller Sync
- `GET /api/sync/status` - Sync-Status
- `GET /api/export/csv` - CSV-Export

## 🚀 Produktionsdeployment

Für den Produktionseinsatz empfehlen wir:

### Mit Gunicorn (Linux/Mac)

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

### Mit Nginx als Reverse Proxy

```nginx
server {
    listen 80;
    server_name ihr-domain.de;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Umgebungsvariablen

```bash
export FLASK_ENV=production
export SECRET_KEY=ihr-geheimer-schluessel
python app.py
```

## 📝 Lizenz

Dieses Projekt steht zur freien Verfügung.

## 🤝 Beiträge

Verbesserungsvorschläge und Pull Requests sind willkommen!

## 📧 Support

Bei Fragen oder Problemen können Sie ein Issue erstellen.

## 🎯 Roadmap

Geplante Features:
- [ ] Barcode-Scanner Integration
- [ ] Mehrsprachigkeit
- [ ] Benutzer- und Rechteverwaltung
- [ ] Mobile App
- [ ] Lieferanten-Bestellungen
- [ ] Inventur-Modus
- [ ] Berichte und Statistiken
- [ ] Bilder für Artikel
- [ ] Email-Benachrichtigungen bei niedrigem Bestand

---

**Viel Erfolg mit Ihrer Lagerverwaltung! 📦✨**
