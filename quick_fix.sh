#!/bin/bash
# Quick Fix für StockMaster

echo "Stoppe StockMaster Service..."
sudo systemctl stop stockmaster

echo "Wechsle ins Verzeichnis..."
cd /home/stockmaster/stockmaster

echo "Aktiviere Virtual Environment..."
source venv/bin/activate

echo "Teste App-Import..."
python3 -c "import app" || {
    echo "FEHLER: App kann nicht importiert werden!"
    echo "Prüfe die Logs:"
    tail -20 /home/stockmaster/stockmaster/logs/gunicorn-error.log
    exit 1
}

echo "Starte Gunicorn im Vordergrund (zum Testen)..."
echo "Drücke Ctrl+C zum Beenden, dann Service wieder starten"
echo ""
gunicorn -c gunicorn_config.py app:app
