#!/bin/bash

# Farbcodes für bessere Lesbarkeit
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  📦 Lagerverwaltung Startskript${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Prüfe ob Python installiert ist
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 ist nicht installiert!${NC}"
    echo "Bitte installieren Sie Python 3.8 oder höher."
    exit 1
fi

echo -e "${GREEN}✓ Python gefunden:${NC} $(python3 --version)"

# Prüfe ob venv existiert
if [ ! -d "venv" ]; then
    echo ""
    echo -e "${YELLOW}⚠ Virtuelle Umgebung nicht gefunden. Erstelle neue venv...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtuelle Umgebung erstellt${NC}"
fi

# Aktiviere venv
echo ""
echo -e "${BLUE}→ Aktiviere virtuelle Umgebung...${NC}"
source venv/bin/activate

# Prüfe/Installiere Dependencies
echo ""
echo -e "${BLUE}→ Prüfe Python-Pakete...${NC}"
if ! pip show flask &> /dev/null; then
    echo -e "${YELLOW}⚠ Installiere benötigte Pakete...${NC}"
    pip install -r requirements.txt
    echo -e "${GREEN}✓ Pakete installiert${NC}"
else
    echo -e "${GREEN}✓ Alle Pakete vorhanden${NC}"
fi

# Prüfe ob credentials.json existiert
if [ ! -f "credentials.json" ]; then
    echo ""
    echo -e "${YELLOW}⚠ Google Drive credentials.json nicht gefunden!${NC}"
    echo "Für Google Drive Sync benötigen Sie:"
    echo "1. Google Cloud Projekt erstellen"
    echo "2. Google Drive API aktivieren"
    echo "3. OAuth 2.0 Desktop Credentials herunterladen"
    echo "4. Als 'credentials.json' speichern"
    echo ""
    echo "Siehe README.md für detaillierte Anleitung."
    echo ""
    read -p "Trotzdem fortfahren? (j/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Jj]$ ]]; then
        exit 1
    fi
fi

# Starte die Anwendung
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  🚀 Starte Lagerverwaltung...${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Anwendung läuft auf:${NC} http://localhost:5000"
echo ""
echo -e "${YELLOW}Drücken Sie STRG+C zum Beenden${NC}"
echo ""

python3 app.py
