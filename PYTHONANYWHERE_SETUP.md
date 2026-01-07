# StockMaster auf PythonAnywhere deployen
## Schritt-für-Schritt Anleitung

---

## SCHRITT 1: Account erstellen (5 Minuten)

1. Gehen Sie zu: **https://www.pythonanywhere.com**
2. Klicken Sie oben rechts auf **"Pricing & signup"**
3. Wählen Sie **"Create a Beginner account"** (KOSTENLOS)
4. Registrieren Sie sich (Username, Email, Passwort)
5. Bestätigen Sie Ihre Email
6. Einloggen

---

## SCHRITT 2: Code hochladen (10 Minuten)

### Option: Manueller Upload (EINFACHSTE METHODE)

1. **Dashboard → "Files"**

2. **Neuen Ordner erstellen:**
   - Eingabefeld "Directories": `/home/IhrUsername/stockmaster`
   - Enter drücken

3. **In den Ordner navigieren:**
   - Klick auf `stockmaster`

4. **Dateien einzeln hochladen:**
   - Button "Upload a file"
   - Laden Sie diese Dateien hoch:
     - `app.py`
     - `requirements.txt`
     - `auto_backup.py`
     - `notification_service.py`
     - `email_service.py`

5. **Ordner hochladen:**
   - Erstellen Sie Unterordner: `static` und `templates`
   - Laden Sie alle Dateien aus diesen Ordnern hoch
   - Für `static`: Alle .js, .css Dateien + Unterordner `icons`
   - Für `templates`: `index.html`, `login.html`, `offline.html`

---

## SCHRITT 3: Python-Packages installieren (5 Minuten)

1. **Dashboard → "Consoles" → "Bash"**

2. **In der Console eingeben:**
   ```bash
   cd stockmaster
   python3.10 -m venv venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Warten bis fertig** (kann 2-3 Minuten dauern)

---

## SCHRITT 4: Datenbank erstellen (2 Minuten)

1. **In der gleichen Bash Console:**
   ```bash
   python app.py
   ```

2. **Sie sehen:**
   ```
   Database initialized
   Admin-Benutzer erstellt
   ```

3. **Beenden mit:** `Ctrl + C`

---

## SCHRITT 5: Web App einrichten (10 Minuten)

1. **Dashboard → "Web" → "Add a new web app"**

2. **Wizard durchgehen:**
   - "Next" klicken
   - Framework: **Flask** wählen
   - Python: **3.10** wählen
   - Pfad: `/home/IhrUsername/stockmaster/app.py`
   - "Next"

3. **Konfiguration anpassen:**

   **Virtualenv-Pfad:**
   ```
   /home/IhrUsername/stockmaster/venv
   ```

   **WSGI Configuration File:**
   - Klicken Sie auf den WSGI-Link
   - ALLES löschen
   - Einfügen:
   ```python
   import sys
   import os

   path = '/home/IhrUsername/stockmaster'
   if path not in sys.path:
       sys.path.insert(0, path)

   os.chdir(path)

   from app import app as application
   ```
   - **WICHTIG: Ersetzen Sie `IhrUsername` mit Ihrem echten Username!**
   - Speichern

4. **Static Files:**
   - Scrollen zu "Static files"
   - URL: `/static/`
   - Directory: `/home/IhrUsername/stockmaster/static`

---

## SCHRITT 6: Live gehen! (1 Minute)

1. **Web-Tab → Großer grüner Button:**
   ```
   ⟳ Reload IhrUsername.pythonanywhere.com
   ```

2. **Ihre App läuft jetzt auf:**
   ```
   https://IhrUsername.pythonanywhere.com
   ```

3. **Öffnen Sie die URL im Browser!**

4. **Login:**
   - Username: `admin`
   - Passwort: `admin123` (standardmäßig)

---

## FERTIG! 🎉

Ihre App ist jetzt online und weltweit erreichbar!

---

## WICHTIG: Passwort ändern

1. Nach erstem Login
2. Einstellungen → Benutzer → Admin bearbeiten
3. Neues sicheres Passwort setzen

---

## FEHLERBEHEBUNG

### "500 Internal Server Error"

**Lösung 1: Error Log checken**
- Web → "Log files" → "Error log"
- Letzten Fehler lesen

**Häufigste Ursache: Package fehlt**
```bash
cd stockmaster
source venv/bin/activate
pip install flask flask-limiter flask-talisman python-dotenv
pip install reportlab openpyxl qrcode python-barcode pillow
```
Web → Reload

### "ImportError"

```bash
cd stockmaster
source venv/bin/activate
pip install -r requirements.txt --force-reinstall
```
Web → Reload

### Login funktioniert nicht

```bash
cd stockmaster
python
```
```python
from app import init_db
init_db()
exit()
```
Web → Reload

---

## CODE AKTUALISIEREN

Nach Änderungen lokal:

1. **Files → Datei wählen → Upload**
2. **Web → Reload**

---

## NÄCHSTE SCHRITTE

- ✅ App testen
- ✅ Artikel anlegen
- ✅ Barcode-Scanner testen (funktioniert über HTTPS!)
- ✅ Andere Benutzer einladen
- ✅ Regelmäßige Backups

Viel Erfolg! 🚀
