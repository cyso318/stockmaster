# Auto-Backup System für StockMaster

## Übersicht

StockMaster verfügt über ein automatisches Backup-System, das regelmäßig Backups der Datenbank zu Google Drive hochlädt.

## Features

- ✅ **Automatische Backups**: Backups werden automatisch in konfigurierbaren Intervallen erstellt
- ✅ **Google Drive Integration**: Alle Backups werden sicher in Google Drive gespeichert
- ✅ **Backup-Rotation**: Alte Backups werden automatisch gelöscht, nur die neuesten werden behalten
- ✅ **Status-Monitoring**: Echtzeit-Status im Burger-Menü der App
- ✅ **Manuelle Backups**: Jederzeit manuell ein Backup erstellen
- ✅ **Background-Service**: Läuft als Daemon-Thread im Hintergrund

## Konfiguration

### Umgebungsvariablen

Erstellen Sie eine `.env` Datei oder setzen Sie folgende Umgebungsvariablen:

```bash
# Auto-Backup aktivieren/deaktivieren
AUTO_BACKUP_ENABLED=true

# Backup-Intervall in Stunden (Standard: 24 Stunden = täglich)
BACKUP_INTERVAL_HOURS=24

# Anzahl der zu behaltenden Backups (Standard: 30)
KEEP_BACKUPS=30
```

### Beispiel-Konfigurationen

#### Tägliches Backup (Standard)
```bash
AUTO_BACKUP_ENABLED=true
BACKUP_INTERVAL_HOURS=24
KEEP_BACKUPS=30
```

#### Stündliches Backup
```bash
AUTO_BACKUP_ENABLED=true
BACKUP_INTERVAL_HOURS=1
KEEP_BACKUPS=168  # 1 Woche bei stündlichen Backups
```

#### Wöchentliches Backup
```bash
AUTO_BACKUP_ENABLED=true
BACKUP_INTERVAL_HOURS=168  # 7 Tage * 24 Stunden
KEEP_BACKUPS=12  # 12 Wochen = ~3 Monate
```

#### Backup deaktivieren
```bash
AUTO_BACKUP_ENABLED=false
```

## Google Drive Setup

### Voraussetzungen

1. Ein Google Cloud Projekt
2. Google Drive API aktiviert
3. OAuth 2.0 Credentials (credentials.json)

### Schritt-für-Schritt-Anleitung

1. **Google Cloud Projekt erstellen**
   - Gehen Sie zu: https://console.cloud.google.com/
   - Erstellen Sie ein neues Projekt oder wählen Sie ein bestehendes aus

2. **Google Drive API aktivieren**
   - Navigieren Sie zu "APIs & Services" > "Library"
   - Suchen Sie nach "Google Drive API"
   - Klicken Sie auf "Aktivieren"

3. **OAuth 2.0 Credentials erstellen**
   - Gehen Sie zu "APIs & Services" > "Credentials"
   - Klicken Sie auf "+ CREATE CREDENTIALS" > "OAuth client ID"
   - Wählen Sie "Desktop app" als Application type
   - Geben Sie einen Namen ein (z.B. "StockMaster Backup")
   - Laden Sie die `credentials.json` herunter

4. **credentials.json installieren**
   - Legen Sie die heruntergeladene `credentials.json` im Root-Verzeichnis der App ab
   - Beim ersten Start wird ein Browser-Fenster geöffnet
   - Melden Sie sich mit Ihrem Google-Account an und geben Sie die Berechtigung
   - Ein `token.pickle` wird erstellt für zukünftige Authentifizierungen

## Verwendung

### Automatisch

Nach dem Start der App läuft das Auto-Backup-System automatisch im Hintergrund:

```bash
python app.py
```

Sie sehen eine Bestätigung in der Console:
```
✓ Automatisches Backup aktiviert (Intervall: 24h, behalte: 30 Backups)
```

### Manuell über die UI

1. Öffnen Sie das Burger-Menü (☰) im Header
2. Klicken Sie auf "Backup erstellen"
3. Eine Erfolgsmeldung zeigt den Backup-Status an

### Manuell per API

```bash
curl -X POST http://localhost:5000/api/backup/manual \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: <token>"
```

### Status abfragen

```bash
curl http://localhost:5000/api/backup/status
```

Response:
```json
{
  "is_running": true,
  "backup_interval_hours": 24,
  "last_backup_time": "2026-01-06T14:30:00",
  "last_backup_status": "success",
  "next_backup_time": "2026-01-07T14:30:00",
  "backup_count": 5,
  "keep_backups": 30
}
```

## Backup-Dateien

### Dateiformat

Backups werden mit folgendem Namensschema gespeichert:
```
inventory_backup_YYYYMMDD_HHMMSS.db
```

Beispiel: `inventory_backup_20260106_143000.db`

### Speicherort in Google Drive

Alle Backups werden in einem dedizierten Ordner gespeichert:
```
Google Drive/
  └── Lagerverwaltung_Backups/
      ├── inventory_backup_20260106_143000.db
      ├── inventory_backup_20260105_143000.db
      └── ...
```

## Troubleshooting

### Auto-Backup startet nicht

**Problem**: Fehlermeldung beim Start
```
⚠️ Auto-Backup konnte nicht gestartet werden: No module named 'schedule'
```

**Lösung**: Installieren Sie die fehlenden Dependencies:
```bash
pip install -r requirements.txt
```

### Authentifizierung fehlgeschlagen

**Problem**: "Authentifizierung fehlgeschlagen" bei Backup-Versuch

**Lösung**:
1. Überprüfen Sie, ob `credentials.json` existiert
2. Löschen Sie `token.pickle` und authentifizieren Sie sich neu:
   ```bash
   rm token.pickle
   python gdrive_sync.py
   ```

### Keine Verbindung zu Google Drive

**Problem**: Backup schlägt fehl mit Netzwerkfehler

**Lösung**:
1. Überprüfen Sie Ihre Internetverbindung
2. Prüfen Sie, ob die Google Drive API in Ihrem Projekt aktiviert ist
3. Überprüfen Sie Firewall-Einstellungen

### Backups werden nicht gelöscht

**Problem**: Zu viele Backups in Google Drive

**Lösung**: Die `cleanup_old_backups` Funktion läuft nach jedem Backup. Prüfen Sie:
- `KEEP_BACKUPS` Umgebungsvariable
- Google Drive Berechtigungen
- Logs für Fehler beim Cleanup

## Logs

Logs werden in die Console ausgegeben:

```
2026-01-06 14:30:00 - auto_backup - INFO - Starte automatisches Backup...
2026-01-06 14:30:05 - auto_backup - INFO - ✓ Backup #1 erfolgreich abgeschlossen
2026-01-06 14:30:05 - auto_backup - INFO -   Datei: inventory_backup_20260106_143000.db
2026-01-06 14:30:05 - auto_backup - INFO -   Link: https://drive.google.com/...
```

## Sicherheit

- ✅ Backups werden verschlüsselt zu Google Drive übertragen (HTTPS)
- ✅ OAuth 2.0 Authentifizierung
- ✅ Tokens werden lokal gespeichert (`token.pickle`)
- ⚠️ **Wichtig**: Fügen Sie `token.pickle` zu `.gitignore` hinzu!
- ⚠️ **Wichtig**: Fügen Sie `credentials.json` zu `.gitignore` hinzu!

## Best Practices

1. **Backup-Intervall**: Wählen Sie basierend auf Ihrer Änderungsrate
   - Hohe Aktivität: Stündlich oder alle 6 Stunden
   - Normale Nutzung: Täglich (Standard)
   - Geringe Aktivität: Wöchentlich

2. **Backup-Retention**:
   - Mindestens 7 Tage für kurze Wiederherstellung
   - 30 Tage (Standard) für mittelfristige Sicherung
   - 90+ Tage für langfristige Archivierung

3. **Monitoring**:
   - Überprüfen Sie regelmäßig den Backup-Status im Burger-Menü
   - Testen Sie gelegentlich die Wiederherstellung

4. **Testing**:
   - Führen Sie nach dem Setup ein manuelles Backup durch
   - Überprüfen Sie Google Drive, ob das Backup erscheint
   - Dokumentieren Sie Ihre Backup-Strategie

## Erweiterte Nutzung

### Standalone-Backup-Script

Sie können das Auto-Backup-System auch standalone testen:

```bash
python auto_backup.py
```

Dies startet einen Test-Service mit 6-Minuten-Intervall.

### Programmatische Nutzung

```python
from auto_backup import get_backup_service

# Service erstellen
service = get_backup_service(
    db_path='inventory.db',
    backup_interval_hours=24,
    keep_backups=30
)

# Service starten
service.start()

# Manuelles Backup
result = service.manual_backup()

# Status abfragen
status = service.get_status()

# Service stoppen
service.stop()
```

## Support

Bei Problemen oder Fragen:
1. Überprüfen Sie diese Dokumentation
2. Schauen Sie in die Logs
3. Erstellen Sie ein Issue auf GitHub
