# Google Drive Backup Setup für Server

## Schritt 1: Auf Windows-PC authentifizieren

**Wichtig:** Dieser Schritt muss nur EINMAL gemacht werden!

```bash
cd C:\Users\robin\OneDrive\Desktop\stockmaster

# Virtual Environment aktivieren (falls vorhanden)
venv\Scripts\activate

# Test-Authentifizierung durchführen
python -c "from gdrive_sync import GoogleDriveSync; sync = GoogleDriveSync(); sync.authenticate(); print('✓ Authentifizierung erfolgreich!')"
```

**Was passiert:**
- Ein Browser-Fenster öffnet sich
- Sie werden gebeten, sich bei Google anzumelden
- Erlauben Sie StockMaster den Zugriff auf Google Drive
- Eine Datei `token.pickle` wird erstellt

## Schritt 2: Dateien zum Server hochladen

```bash
# token.pickle hochladen (enthält Authentifizierungs-Token)
scp "C:\Users\robin\OneDrive\Desktop\stockmaster\token.pickle" stockmaster@87.106.4.172:/home/stockmaster/stockmaster/

# credentials.json hochladen (falls noch nicht auf Server)
scp "C:\Users\robin\OneDrive\Desktop\stockmaster\credentials.json" stockmaster@87.106.4.172:/home/stockmaster/stockmaster/

# gdrive_sync.py hochladen (aktualisierte Version)
scp "C:\Users\robin\OneDrive\Desktop\stockmaster\gdrive_sync.py" stockmaster@87.106.4.172:/home/stockmaster/stockmaster/
```

## Schritt 3: Auf Server testen

```bash
ssh stockmaster@87.106.4.172

cd /home/stockmaster/stockmaster
source venv/bin/activate

# Test ob Google Drive funktioniert
python3 -c "from gdrive_sync import GoogleDriveSync; sync = GoogleDriveSync(); sync.authenticate(); print('✓ Google Drive verbunden!')"
```

Wenn das funktioniert, sehen Sie: `✓ Google Drive verbunden!`

## Schritt 4: Automatisches Backup testen

```bash
# Im Dashboard auf "Backup erstellen" klicken
# Oder manuell:
python3 -c "from auto_backup import create_backup; create_backup()"
```

Das Backup sollte jetzt zu Google Drive hochgeladen werden!

## Schritt 5: Service neu starten

```bash
sudo systemctl restart stockmaster
```

---

## Troubleshooting

### Problem: "token.pickle expired"

Das Token läuft nach einiger Zeit ab. Lösung:

1. **Automatische Erneuerung:** Der Code versucht automatisch, das Token zu erneuern
2. **Manuelle Erneuerung:** Wiederholen Sie Schritt 1 auf Windows

### Problem: "credentials.json nicht gefunden"

Laden Sie `credentials.json` von Google Cloud Console herunter:
1. https://console.cloud.google.com/apis/credentials
2. OAuth 2.0 Client ID → Download als `credentials.json`

### Problem: "Permission denied"

Berechtigungen setzen:
```bash
chmod 644 /home/stockmaster/stockmaster/token.pickle
chmod 644 /home/stockmaster/stockmaster/credentials.json
```

---

## Token-Gültigkeit

- **token.pickle** ist ca. 7 Tage gültig
- Nach Ablauf wird es automatisch erneuert (wenn `refresh_token` vorhanden)
- Falls Erneuerung fehlschlägt: Schritt 1 wiederholen

---

## Backup-Frequenz einstellen

In der `.env` Datei:
```bash
BACKUP_INTERVAL_HOURS=24  # Täglich
```

Oder in `auto_backup.py` anpassen.

---

**Stand:** Januar 2025
