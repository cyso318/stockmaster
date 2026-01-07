#!/bin/bash
# Fix für Session-Problem auf Ubuntu Server
# Dieses Script behebt das Problem, dass nach Login zur Landing Page zurückgekehrt wird

echo "========================================="
echo "StockMaster Session-Fix Script"
echo "========================================="
echo ""

# 1. Backup der aktuellen Nginx-Config
echo "[1/5] Backup der Nginx-Konfiguration..."
sudo cp /etc/nginx/sites-available/stockmaster /etc/nginx/sites-available/stockmaster.backup
echo "✓ Backup erstellt: /etc/nginx/sites-available/stockmaster.backup"
echo ""

# 2. Nginx-Config aktualisieren
echo "[2/5] Aktualisiere Nginx-Konfiguration..."
sudo tee /etc/nginx/sites-available/stockmaster > /dev/null <<'EOF'
server {
    listen 80;
    server_name _;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;

        # Header für ProxyFix
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;

        # WICHTIG für Sessions: Cookie-Header durchreichen
        proxy_set_header Cookie $http_cookie;
        proxy_pass_header Set-Cookie;

        proxy_redirect off;
        proxy_buffering off;

        # Timeouts erhöhen
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
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
EOF
echo "✓ Nginx-Konfiguration aktualisiert"
echo ""

# 3. Nginx-Config testen
echo "[3/5] Teste Nginx-Konfiguration..."
if sudo nginx -t; then
    echo "✓ Nginx-Konfiguration ist gültig"
else
    echo "✗ FEHLER: Nginx-Konfiguration ungültig!"
    echo "Stelle alte Konfiguration wieder her..."
    sudo mv /etc/nginx/sites-available/stockmaster.backup /etc/nginx/sites-available/stockmaster
    exit 1
fi
echo ""

# 4. Services neu starten
echo "[4/5] Starte Services neu..."
sudo systemctl restart stockmaster
sudo systemctl restart nginx
echo "✓ Services neu gestartet"
echo ""

# 5. Status prüfen
echo "[5/5] Prüfe Service-Status..."
if sudo systemctl is-active --quiet stockmaster; then
    echo "✓ StockMaster läuft"
else
    echo "✗ WARNUNG: StockMaster läuft nicht!"
    echo "Prüfe Logs mit: sudo journalctl -u stockmaster -n 50"
fi

if sudo systemctl is-active --quiet nginx; then
    echo "✓ Nginx läuft"
else
    echo "✗ WARNUNG: Nginx läuft nicht!"
fi
echo ""

echo "========================================="
echo "Fix abgeschlossen!"
echo "========================================="
echo ""
echo "Nächste Schritte:"
echo "1. Öffne http://$(hostname -I | awk '{print $1}')/login"
echo "2. Melde dich an mit: admin / admin123"
echo "3. Du solltest jetzt zum Dashboard weitergeleitet werden"
echo ""
echo "Wenn es immer noch nicht funktioniert:"
echo "- Prüfe Logs: sudo journalctl -u stockmaster -f"
echo "- Öffne Debug-Seite: http://$(hostname -I | awk '{print $1}')/debug-session"
echo ""
