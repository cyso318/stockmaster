#!/bin/bash
# Debug-Script für StockMaster Server

echo "========================================="
echo "StockMaster Server Debug"
echo "========================================="
echo ""

# 1. Service Status
echo "[1] Service Status:"
echo "-------------------"
sudo systemctl status stockmaster --no-pager -l
echo ""

# 2. Gunicorn läuft?
echo "[2] Gunicorn Prozesse:"
echo "----------------------"
ps aux | grep gunicorn | grep -v grep
echo ""

# 3. Port 8000 offen?
echo "[3] Port 8000 Status:"
echo "---------------------"
sudo netstat -tlnp | grep 8000 || echo "Port 8000 nicht offen!"
echo ""

# 4. Letzte Fehler aus Logs
echo "[4] Letzte Gunicorn Errors (10 Zeilen):"
echo "----------------------------------------"
tail -10 /home/stockmaster/stockmaster/logs/gunicorn-error.log 2>/dev/null || echo "Keine Error-Log gefunden"
echo ""

# 5. Systemd Journal
echo "[5] Letzte Systemd Logs (15 Zeilen):"
echo "-------------------------------------"
sudo journalctl -u stockmaster -n 15 --no-pager
echo ""

# 6. Test: Kann Gunicorn die App laden?
echo "[6] Test: App Import:"
echo "---------------------"
cd /home/stockmaster/stockmaster
source venv/bin/activate
python3 -c "import app; print('✓ App kann importiert werden')" 2>&1 || echo "✗ App kann NICHT importiert werden!"
echo ""

# 7. Test: Localhost-Verbindung
echo "[7] Test: Localhost auf Port 8000:"
echo "-----------------------------------"
curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" http://localhost:8000/ || echo "Keine Verbindung möglich"
echo ""

# 8. .env Datei vorhanden?
echo "[8] .env Datei Check:"
echo "---------------------"
if [ -f /home/stockmaster/stockmaster/.env ]; then
    echo "✓ .env existiert"
    echo "SECRET_KEY gesetzt: $(grep -q SECRET_KEY /home/stockmaster/stockmaster/.env && echo 'Ja' || echo 'NEIN!')"
else
    echo "✗ .env FEHLT!"
fi
echo ""

# 9. Dateiberechtigungen
echo "[9] Dateiberechtigungen:"
echo "------------------------"
ls -la /home/stockmaster/stockmaster/app.py
ls -la /home/stockmaster/stockmaster/inventory.db 2>/dev/null || echo "Datenbank fehlt!"
echo ""

echo "========================================="
echo "Debug-Info gesammelt"
echo "========================================="
