# WINDOWS INSTALLATION - Schritt für Schritt

## Schnellstart (Einfachste Methode)

1. Öffnen Sie die **Eingabeaufforderung** (CMD) im Projektordner:
   - Im Windows Explorer zum Ordner navigieren
   - In die Adressleiste klicken und "cmd" eingeben
   - Enter drücken

2. Führen Sie folgende Befehle nacheinander aus:

```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

3. Browser öffnen: http://localhost:5000

## Alternative: PowerShell

1. Öffnen Sie **PowerShell** im Projektordner:
   - Rechtsklick im Ordner → "In PowerShell öffnen"

2. Führen Sie aus:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Falls Fehler "Ausführung von Skripts ist deaktiviert":
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Ohne virtuelle Umgebung (Nicht empfohlen)

Wenn die virtuelle Umgebung Probleme macht:

```cmd
pip install Flask google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
python app.py
```

## Fehlerbehandlung

### "Python ist nicht installiert"
- Laden Sie Python von https://www.python.org/downloads/ herunter
- Bei Installation: Haken bei "Add Python to PATH" setzen!
- Nach Installation CMD neu öffnen

### "pip ist nicht installiert"
```cmd
python -m ensurepip --upgrade
```

### "ModuleNotFoundError: No module named 'flask'"
```cmd
pip install Flask
```

Oder alle Pakete einzeln:
```cmd
pip install Flask
pip install google-auth
pip install google-auth-oauthlib
pip install google-auth-httplib2
pip install google-api-python-client
```

### Port 5000 ist bereits belegt
Öffnen Sie `app.py` und ändern Sie die letzte Zeile:
```python
app.run(debug=True, host='0.0.0.0', port=5001)
```

## Nach erfolgreicher Installation

Die Anwendung läuft nun auf:
- http://localhost:5000
- oder http://127.0.0.1:5000

Zum Beenden: STRG+C in der Eingabeaufforderung drücken

## Nächste Schritte

1. Kategorien anlegen (Tab "Kategorien")
2. Standorte anlegen (Tab "Standorte")
3. Artikel hinzufügen (Tab "Artikel")
4. Bestandsbuchungen durchführen

## Google Drive Setup (Optional)

Siehe README.md für die komplette Google Drive Anleitung.
Die Anwendung funktioniert auch ohne Google Drive!
