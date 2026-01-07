# 🚀 Quick Start Guide

Schnellanleitung für die Lagerverwaltung in 5 Minuten!

## Schritt 1: Installation

### Windows
```batch
# Doppelklick auf start.bat
```

### Linux/Mac
```bash
chmod +x start.sh
./start.sh
```

Oder manuell:
```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Schritt 2: Anwendung öffnen

Öffnen Sie im Browser: **http://localhost:5000**

## Schritt 3: Erste Schritte

### 1. Kategorien anlegen
- Wechseln Sie zum Tab "Kategorien"
- Klicken Sie auf "+ Neue Kategorie"
- Beispiele: Elektronik, Büromaterial, Werkzeuge

### 2. Standorte anlegen
- Wechseln Sie zum Tab "Standorte"
- Klicken Sie auf "+ Neuer Standort"
- Beispiele: Lager A, Regal 1, Büro

### 3. Ersten Artikel anlegen
- Wechseln Sie zum Tab "Artikel"
- Klicken Sie auf "+ Neuer Artikel"
- Füllen Sie die Felder aus:
  - Name: z.B. "USB-Stick 32GB"
  - SKU: z.B. "USB-32-001" (optional)
  - Kategorie: Wählen Sie "Elektronik"
  - Standort: Wählen Sie "Lager A"
  - Menge: z.B. 10
  - Mindestbestand: z.B. 5
  - Preis: z.B. 8.99 €
- Speichern Sie den Artikel

### 4. Bestandsbuchung durchführen
- Bei Ihrem Artikel klicken Sie auf "Einbuchen" oder "Ausbuchen"
- Geben Sie die Menge ein
- Optional: Referenz und Notizen
- Bestätigen Sie die Buchung

## Schritt 4: Google Drive Sync (Optional)

### Voraussetzungen
1. Google Account
2. Google Cloud Console Zugang

### Setup
1. Gehen Sie zu: https://console.cloud.google.com/
2. Erstellen Sie ein neues Projekt
3. Aktivieren Sie "Google Drive API"
4. Erstellen Sie OAuth 2.0 Desktop Credentials
5. Laden Sie `credentials.json` herunter
6. Speichern Sie es im Projektverzeichnis
7. Klicken Sie in der App auf "Sync zu Google Drive"
8. Beim ersten Mal: Browser-Authentifizierung

## Schritt 5: Features nutzen

### Suche & Filter
- Suchleiste: Suche nach Name, SKU oder Beschreibung
- Filter: Nach Kategorie oder Standort filtern
- Button "Niedriger Bestand": Zeigt Artikel unter Mindestbestand

### CSV Export
- Klicken Sie auf "CSV Export" im Header
- Alle Artikel werden exportiert
- Öffnen Sie mit Excel oder ähnlichem

### Dashboard
- Zeigt wichtige Kennzahlen auf einen Blick
- Aktualisiert sich automatisch
- Gesamtwert basiert auf Menge × Preis

## Tipps & Tricks

### Effektive Nutzung
1. **SKU verwenden**: Macht Artikel eindeutig identifizierbar
2. **Kategorien**: Strukturieren Sie nach Produktgruppen
3. **Standorte**: Nutzen Sie hierarchische Namen (z.B. "Lager-A-R1-F2")
4. **Mindestbestand**: Setzen Sie sinnvolle Werte für Nachbestellung
5. **Notizen**: Wichtige Infos zu Artikeln festhalten

### Wartung
- **Regelmäßige Backups**: Nutzen Sie den Google Drive Sync
- **CSV Export**: Erstellen Sie gelegentlich manuelle Backups
- **Datenbank**: Die `inventory.db` Datei kann kopiert werden

### Sicherheit
- Ändern Sie `SECRET_KEY` in app.py für Produktion
- Sichern Sie `credentials.json` und `token.pickle`
- Nutzen Sie HTTPS in der Produktion

## Häufige Fragen

**Q: Kann ich Bilder zu Artikeln hinzufügen?**
A: Derzeit nicht, aber geplant für zukünftige Versionen.

**Q: Unterstützt die App Barcode-Scanning?**
A: Noch nicht implementiert, steht auf der Roadmap.

**Q: Kann ich mehrere Benutzer anlegen?**
A: Aktuell keine Benutzerverwaltung. Für Multi-User siehe Roadmap.

**Q: Läuft die App offline?**
A: Ja, außer für den Google Drive Sync.

**Q: Wie kann ich Daten importieren?**
A: Aktuell nur manuell. CSV-Import ist geplant.

## Support

Bei Problemen:
1. Prüfen Sie die README.md
2. Schauen Sie in die Konsole für Fehlermeldungen
3. Erstellen Sie ein Issue auf GitHub

## Nächste Schritte

- Erkunden Sie alle Features
- Passen Sie die Anwendung an Ihre Bedürfnisse an
- Geben Sie Feedback für Verbesserungen

**Viel Erfolg! 📦✨**
