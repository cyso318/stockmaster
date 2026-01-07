# StockMaster - Deployment Guide
## Ihre App als richtige Webseite veröffentlichen

---

## Option 1: PythonAnywhere (EINFACHSTE LÖSUNG - KOSTENLOS)

**Ideal für:** Anfänger, kostenlose Hosting-Option, Flask-Apps

### Schritte:

1. **Account erstellen:**
   - Gehen Sie zu: https://www.pythonanywhere.com
   - Klicken Sie auf "Pricing & signup"
   - Wählen Sie "Create a Beginner account" (KOSTENLOS)
   - Registrieren Sie sich mit E-Mail

2. **Code hochladen:**
   - Im Dashboard: Klicken Sie auf "Files"
   - Erstellen Sie Ordner: `/home/IhrUsername/stockmaster`
   - Laden Sie alle Dateien hoch (oder nutzen Sie Git)

3. **Web-App einrichten:**
   - Dashboard → "Web" → "Add a new web app"
   - Framework: "Flask"
   - Python-Version: 3.10
   - Pfad zu app.py: `/home/IhrUsername/stockmaster/app.py`

4. **Datenbank einrichten:**
   - Bash-Konsole öffnen
   - ```bash
     cd stockmaster
     python app.py  # Erstellt inventory.db
     ```

5. **Umgebungsvariablen setzen:**
   - Web → Environment variables
   - Fügen Sie Ihre .env Variablen hinzu

6. **App starten:**
   - Web → Reload
   - Ihre App läuft jetzt auf: `IhrUsername.pythonanywhere.com`

**Vorteile:**
- ✓ Kostenlos
- ✓ Sehr einfach
- ✓ HTTPS inklusive
- ✓ Für Flask optimiert

**Nachteile:**
- Begrenzt auf 512 MB Storage
- Täglich nur begrenzte CPU-Zeit
- App "schläft" nach Inaktivität

---

## Option 2: Render.com (MODERN & EINFACH)

**Ideal für:** Moderne Deployment-Lösung, automatische Updates

### Schritte:

1. **Code zu GitHub:**
   - Erstellen Sie GitHub-Account: https://github.com
   - Repository erstellen: "stockmaster"
   - Code hochladen:
     ```bash
     git init
     git add .
     git commit -m "Initial commit"
     git remote add origin https://github.com/IhrUsername/stockmaster.git
     git push -u origin main
     ```

2. **Render Account:**
   - Gehen Sie zu: https://render.com
   - "Get Started for Free"
   - Mit GitHub verbinden

3. **Web Service erstellen:**
   - Dashboard → "New +" → "Web Service"
   - Repository auswählen: stockmaster
   - Name: stockmaster
   - Environment: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`

4. **Umgebungsvariablen:**
   - Im Service → "Environment"
   - Alle .env Variablen hinzufügen

5. **Datenbank (PostgreSQL):**
   - "New +" → "PostgreSQL"
   - Name: stockmaster-db
   - Free tier wählen
   - Mit Web Service verbinden

**Vorteile:**
- ✓ Kostenloser Tier verfügbar
- ✓ Automatische Deployments bei Git-Push
- ✓ HTTPS inklusive
- ✓ Moderne Plattform

**Nachteile:**
- Free tier hat Limits
- App "schläft" nach 15 Min Inaktivität

**Benötigte Dateien:**

`requirements.txt` (bereits vorhanden)

`Procfile` (neu erstellen):
```
web: gunicorn app:app --bind 0.0.0.0:$PORT
```

---

## Option 3: Heroku (BELIEBT)

**Ideal für:** Bewährte Plattform, viele Addons

### Schritte:

1. **Heroku Account:**
   - https://heroku.com
   - Sign up (kostenlos)

2. **Heroku CLI installieren:**
   - https://devcenter.heroku.com/articles/heroku-cli

3. **App erstellen:**
   ```bash
   heroku login
   heroku create stockmaster-app
   ```

4. **Deployment:**
   ```bash
   git init
   git add .
   git commit -m "Initial"
   heroku git:remote -a stockmaster-app
   git push heroku main
   ```

5. **Datenbank einrichten:**
   ```bash
   heroku addons:create heroku-postgresql:mini
   ```

**Vorteile:**
- ✓ Sehr beliebt
- ✓ Viele Add-ons verfügbar
- ✓ Gute Dokumentation

**Nachteile:**
- Kostenloser Tier wurde eingestellt
- Mindestens $5/Monat

**Benötigte Dateien:**

`Procfile`:
```
web: gunicorn app:app
```

`runtime.txt`:
```
python-3.11.0
```

---

## Option 4: Google Cloud Run (FÜR FORTGESCHRITTENE)

**Ideal für:** Skalierbare Lösung, Pay-per-use

### Voraussetzungen:
- Docker installieren
- Google Cloud Account

### Schritte:

1. **Dockerfile erstellen:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
```

2. **Build & Deploy:**
```bash
gcloud run deploy stockmaster \
  --source . \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated
```

**Vorteile:**
- ✓ Extrem skalierbar
- ✓ Nur zahlen wenn genutzt
- ✓ Google-Infrastruktur

**Nachteile:**
- Komplexer Setup
- Kann teuer werden bei viel Traffic

---

## Option 5: Eigener VPS (VOLLE KONTROLLE)

**Ideal für:** Maximale Kontrolle, keine Limits

### Anbieter:
- **Hetzner Cloud** (günstig, Deutschland): ab 4,51€/Monat
- **DigitalOcean** (beliebt): ab $4/Monat
- **Linode** (zuverlässig): ab $5/Monat

### Schritte (Beispiel Hetzner):

1. **Server mieten:**
   - https://www.hetzner.com/cloud
   - Ubuntu 22.04 wählen
   - Kleinste Größe reicht (CX11)

2. **Server einrichten:**
```bash
# SSH verbinden
ssh root@IhreServerIP

# Updates installieren
apt update && apt upgrade -y

# Python & Dependencies
apt install python3-pip python3-venv nginx supervisor -y

# Code hochladen
git clone https://github.com/IhrUsername/stockmaster.git
cd stockmaster
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

3. **Gunicorn als Service:**
`/etc/supervisor/conf.d/stockmaster.conf`:
```ini
[program:stockmaster]
directory=/root/stockmaster
command=/root/stockmaster/venv/bin/gunicorn app:app --bind 127.0.0.1:8000
autostart=true
autorestart=true
```

4. **Nginx konfigurieren:**
`/etc/nginx/sites-available/stockmaster`:
```nginx
server {
    listen 80;
    server_name ihre-domain.de;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

5. **SSL mit Let's Encrypt:**
```bash
apt install certbot python3-certbot-nginx -y
certbot --nginx -d ihre-domain.de
```

**Vorteile:**
- ✓ Volle Kontrolle
- ✓ Keine Limits
- ✓ Günstig bei viel Traffic

**Nachteile:**
- Technisches Know-how nötig
- Sie sind für Updates verantwortlich

---

## EMPFEHLUNG für Sie:

### Für den Start: **PythonAnywhere**
- Kostenlos
- In 10 Minuten online
- Keine Kreditkarte nötig
- Perfekt zum Testen

### Später upgraden zu: **Render.com**
- Moderner
- Automatische Deployments
- Bessere Performance
- Kostenloser Tier für kleine Apps

### Für Production: **Eigener VPS (Hetzner)**
- Nur 4,51€/Monat
- Unbegrenzt nutzbar
- Professionell
- Volle Kontrolle

---

## Zusätzliche Anpassungen für Production:

### 1. Gunicorn installieren:
```bash
pip install gunicorn
```

`requirements.txt` ergänzen:
```
gunicorn==21.2.0
```

### 2. Production-Konfiguration:

In `app.py` am Ende ändern:
```python
if __name__ == '__main__':
    # Für lokale Entwicklung
    app.run(debug=True, host='0.0.0.0', port=5000, ssl_context=ssl_context)
else:
    # Für Production (Gunicorn)
    # Debug muss OFF sein!
    app.config['DEBUG'] = False
```

### 3. Umgebungsvariablen:

Erstellen Sie `.env.production`:
```bash
SECRET_KEY=ihr-super-sicherer-random-key-hier
DEBUG=False
DATABASE_URL=postgresql://...  # Falls PostgreSQL
NOTIFICATIONS_ENABLED=true
# ... alle anderen Settings
```

### 4. Datenbank für Production:

Für SQLite (wie aktuell):
- ✓ Funktioniert auf PythonAnywhere
- ✓ Einfach
- ✗ Nicht ideal für viele Nutzer

Für PostgreSQL (empfohlen):
- ✓ Besser für Production
- ✓ Mehr Features
- ✓ Besser für mehrere Nutzer

---

## Domain verbinden:

### Eigene Domain kaufen:
- **Namecheap**: ~$10/Jahr
- **Google Domains**: ~$12/Jahr
- **Ionos**: ~€1/Jahr (erstes Jahr)

### Domain verbinden:
1. Bei Domain-Anbieter DNS-Einstellungen öffnen
2. A-Record erstellen:
   - Name: `@` (oder `www`)
   - Wert: IP-Adresse Ihres Servers
3. Warten (kann bis 48h dauern, meist schneller)

---

## Nächste Schritte:

1. **Entscheiden Sie sich für eine Plattform**
2. **Ich helfe Ihnen beim Setup**
3. **Anpassungen für Production vornehmen**
4. **Deployment durchführen**
5. **Testen**
6. **Live gehen!**

**Welche Option interessiert Sie am meisten?**
