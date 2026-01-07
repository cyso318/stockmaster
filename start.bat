@echo off
cls

echo ========================================
echo   Lagerverwaltung Startskript
echo ========================================
echo.

:: Pruefe ob Python installiert ist
python --version >nul 2>&1
if errorlevel 1 (
    echo Fehler: Python ist nicht installiert!
    echo Bitte installieren Sie Python 3.8 oder hoeher von python.org
    pause
    exit /b 1
)

echo Python gefunden:
python --version
echo.

:: Pruefe ob venv existiert
if not exist "venv" (
    echo Erstelle virtuelle Umgebung...
    python -m venv venv
    if errorlevel 1 (
        echo Fehler beim Erstellen der virtuellen Umgebung!
        pause
        exit /b 1
    )
    echo Virtuelle Umgebung erstellt.
    echo.
)

:: Aktiviere venv
echo Aktiviere virtuelle Umgebung...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo Fehler beim Aktivieren der virtuellen Umgebung!
    pause
    exit /b 1
)
echo.

:: Installiere/Pruefe Dependencies
echo Pruefe Python-Pakete...
pip show flask >nul 2>&1
if errorlevel 1 (
    echo Installiere benoetigte Pakete...
    echo Dies kann einige Minuten dauern...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo Fehler beim Installieren der Pakete!
        pause
        exit /b 1
    )
    echo Pakete erfolgreich installiert.
) else (
    echo Alle Pakete sind bereits installiert.
)
echo.

:: Pruefe ob credentials.json existiert
if not exist "credentials.json" (
    echo ========================================
    echo HINWEIS: Google Drive Sync
    echo ========================================
    echo credentials.json nicht gefunden!
    echo.
    echo Fuer Google Drive Sync benoetigen Sie:
    echo 1. Google Cloud Projekt erstellen
    echo 2. Google Drive API aktivieren
    echo 3. OAuth 2.0 Desktop Credentials herunterladen
    echo 4. Als 'credentials.json' speichern
    echo.
    echo Siehe README.md fuer detaillierte Anleitung.
    echo Die Anwendung funktioniert auch ohne Google Drive Sync.
    echo.
    pause
)

:: Starte die Anwendung
cls
echo ========================================
echo   Starte Lagerverwaltung...
echo ========================================
echo.
echo Die Anwendung laeuft auf:
echo http://localhost:5000
echo.
echo Druecken Sie STRG+C zum Beenden
echo.
echo ========================================
echo.

python app.py

pause
