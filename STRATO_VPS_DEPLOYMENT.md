# StockMaster - Deployment auf Strato VPS

## Voraussetzungen
- Strato VPS Server (Ubuntu/Debian)
- SSH-Zugriff auf den Server
- Domain (optional, kann auch mit IP-Adresse betrieben werden)

---

## TEIL 1: Erste Schritte - Server-Zugriff

### 1.1 SSH-Verbindung herstellen

**Von Windows (PowerShell):**
```bash
ssh root@IHRE_SERVER_IP
```

**Beim ersten Login:**
- Passwort von Strato eingeben
- Passwort ändern (wenn gefordert)

### 1.2 System aktualisieren
```bash
apt update
apt upgrade -y
```

---

## TEIL 2: Server vorbereiten

### 2.1 Python und Dependencies installieren
```bash
# Python 3.10+ installieren
apt install -y python3 python3-pip python3-venv

# Nginx installieren (Webserver)
apt install -y nginx

# Git installieren
apt install -y git

# Weitere Tools
apt install -y supervisor certbot python3-certbot-nginx
```

### 2.2 Benutzer anlegen (Sicherheit!)
```bash
# Neuer Benutzer (nicht als root laufen lassen)
adduser stockmaster
usermod -aG sudo stockmaster

# Zum neuen Benutzer wechseln
su - stockmaster
```

---

## TEIL 3: Code hochladen

### Option A: Mit Git (empfohlen)
```bash
cd /home/stockmaster
git clone https://github.com/cyso318/stockmaster.git
cd stockmaster
```

### Option B: Mit SFTP/SCP (wenn kein Git)
**Von deinem Windows-PC aus:**
```bash
# Mit WinSCP oder:
scp -r "C:\Users\robin\OneDrive\Desktop\inventory-app" stockmaster@IHRE_SERVER_IP:/home/stockmaster/
```

**Dann auf dem Server:**
```bash
cd /home/stockmaster/inventory-app
```

---

## TEIL 4: Python-Umgebung einrichten

### 4.1 Virtual Environment erstellen
```bash
cd /home/stockmaster/stockmaster  # oder inventory-app
python3 -m venv venv
source venv/bin/activate
```

### 4.2 Dependencies installieren
```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn  # Production WSGI Server
```

### 4.3 Datenbank initialisieren
```bash
python3 app.py
# Warten bis "Database initialized" erscheint
# Dann mit Ctrl+C beenden
```

---

## TEIL 5: Gunicorn konfigurieren

### 5.1 Gunicorn-Konfiguration erstellen
```bash
nano /home/stockmaster/stockmaster/gunicorn_config.py
```

**Inhalt:**
```python
import multiprocessing

bind = "127.0.0.1:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Logging
accesslog = "/home/stockmaster/stockmaster/logs/gunicorn-access.log"
errorlog = "/home/stockmaster/stockmaster/logs/gunicorn-error.log"
loglevel = "info"

# Process naming
proc_name = "stockmaster"
```

**Speichern:** `Ctrl+O`, Enter, `Ctrl+X`

### 5.2 Log-Verzeichnis erstellen
```bash
mkdir -p /home/stockmaster/stockmaster/logs
```

### 5.3 Gunicorn testen
```bash
cd /home/stockmaster/stockmaster
source venv/bin/activate
gunicorn -c gunicorn_config.py app:app
```

**Test:** In einem neuen Terminal:
```bash
curl http://localhost:8000
```

Wenn HTML zurückkommt → funktioniert! Mit `Ctrl+C` beenden.

---

## TEIL 6: Systemd Service (Auto-Start)

### 6.1 Service-Datei erstellen
```bash
sudo nano /etc/systemd/system/stockmaster.service
```

**Inhalt:**
```ini
[Unit]
Description=StockMaster Inventory Management
After=network.target

[Service]
Type=notify
User=stockmaster
Group=stockmaster
WorkingDirectory=/home/stockmaster/stockmaster
Environment="PATH=/home/stockmaster/stockmaster/venv/bin"
ExecStart=/home/stockmaster/stockmaster/venv/bin/gunicorn -c gunicorn_config.py app:app
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=always

[Install]
WantedBy=multi-user.target
```

**Speichern:** `Ctrl+O`, Enter, `Ctrl+X`

### 6.2 Service aktivieren und starten
```bash
sudo systemctl daemon-reload
sudo systemctl enable stockmaster
sudo systemctl start stockmaster
sudo systemctl status stockmaster
```

**Sollte anzeigen:** `active (running)`

---

## TEIL 7: Nginx konfigurieren

### 7.1 Nginx-Konfiguration erstellen
```bash
sudo nano /etc/nginx/sites-available/stockmaster
```

**Inhalt (erstmal ohne SSL):**
```nginx
server {
    listen 80;
    server_name IHRE_DOMAIN_ODER_IP;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_buffering off;
    }

    location /static {
        alias /home/stockmaster/stockmaster/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /uploads {
        alias /home/stockmaster/stockmaster/static/uploads;
        expires 7d;
    }
}
```

**WICHTIG:** `IHRE_DOMAIN_ODER_IP` ersetzen mit:
- Deiner Domain (z.B. `stockmaster.example.com`)
- Oder Server-IP (z.B. `123.45.67.89`)

**Speichern:** `Ctrl+O`, Enter, `Ctrl+X`

### 7.2 Site aktivieren
```bash
sudo ln -s /etc/nginx/sites-available/stockmaster /etc/nginx/sites-enabled/
sudo nginx -t  # Konfiguration testen
sudo systemctl restart nginx
```

### 7.3 Firewall konfigurieren
```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

---

## TEIL 8: SSL-Zertifikat (HTTPS)

### 8.1 Nur wenn du eine Domain hast!

```bash
sudo certbot --nginx -d IHRE_DOMAIN
```

**Certbot wird:**
- Zertifikat ausstellen
- Nginx-Config automatisch anpassen
- Auto-Renewal einrichten

**Test:**
```bash
sudo certbot renew --dry-run
```

### 8.2 Wenn du nur IP-Adresse hast

Dann läuft die App über HTTP (Port 80). Für HTTPS brauchst du eine Domain.

---

## TEIL 9: Fertig! 🎉

### App aufrufen:
- **Mit Domain:** `https://IHRE_DOMAIN`
- **Mit IP:** `http://IHRE_SERVER_IP`

### Login:
- **Username:** `admin`
- **Passwort:** `admin123`
- **WICHTIG:** Passwort sofort ändern!

---

## TEIL 10: Wartung & Troubleshooting

### Logs anschauen
```bash
# Gunicorn Logs
tail -f /home/stockmaster/stockmaster/logs/gunicorn-error.log

# Nginx Logs
sudo tail -f /var/log/nginx/error.log

# Systemd Logs
sudo journalctl -u stockmaster -f
```

### Service neu starten
```bash
sudo systemctl restart stockmaster
sudo systemctl restart nginx
```

### Code aktualisieren
```bash
cd /home/stockmaster/stockmaster
git pull  # Oder neue Dateien hochladen
source venv/bin/activate
pip install -r requirements.txt  # Falls neue Packages
sudo systemctl restart stockmaster
```

### Backup erstellen
```bash
# Datenbank sichern
cp /home/stockmaster/stockmaster/inventory.db ~/backup_$(date +%Y%m%d).db

# Komplett-Backup
tar -czf ~/stockmaster_backup_$(date +%Y%m%d).tar.gz /home/stockmaster/stockmaster
```

### Häufige Probleme

**1. "502 Bad Gateway"**
```bash
sudo systemctl status stockmaster
# Falls nicht läuft:
sudo systemctl start stockmaster
```

**2. "Permission Denied" bei uploads**
```bash
sudo chown -R stockmaster:stockmaster /home/stockmaster/stockmaster
chmod -R 755 /home/stockmaster/stockmaster/static
```

**3. Datenbank-Fehler**
```bash
cd /home/stockmaster/stockmaster
source venv/bin/activate
python3 app.py  # Neu initialisieren
```

---

## Performance-Tipps

### Worker-Anzahl anpassen
In `gunicorn_config.py`:
```python
# Für mehr Performance:
workers = 4  # Anzahl CPU-Kerne
worker_class = "gevent"  # Async workers
```

### Nginx Caching
In `/etc/nginx/sites-available/stockmaster`:
```nginx
# Vor dem server {} Block:
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=my_cache:10m max_size=1g inactive=60m;

# In location / Block:
proxy_cache my_cache;
proxy_cache_valid 200 10m;
```

---

## Sicherheit

### 1. SSH absichern
```bash
sudo nano /etc/ssh/sshd_config
```
```
PermitRootLogin no
PasswordAuthentication no  # Nach SSH-Key-Setup
```

### 2. Fail2Ban installieren
```bash
sudo apt install fail2ban
sudo systemctl enable fail2ban
```

### 3. Auto-Updates
```bash
sudo apt install unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

---

## Domain-Setup bei Strato

Falls du eine Domain bei Strato hast:

1. **DNS-Einstellungen:**
   - A-Record: `@` → `IHRE_SERVER_IP`
   - A-Record: `www` → `IHRE_SERVER_IP`

2. **Warten:** DNS-Propagierung dauert 15-60 Minuten

3. **SSL-Zertifikat:** Dann `certbot` ausführen (siehe Teil 8)

---

## Support

Bei Problemen:
- **Logs prüfen** (siehe Teil 10)
- **Service-Status:** `sudo systemctl status stockmaster`
- **Nginx-Status:** `sudo systemctl status nginx`
- **Firewall:** `sudo ufw status`

**Kontakt:** r.weschenfelder@proton.me

---

**Stand:** Januar 2025
**Version:** StockMaster 1.0
