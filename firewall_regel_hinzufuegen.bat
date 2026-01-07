@echo off
echo ================================================
echo Firewall-Regel fuer StockMaster hinzufuegen
echo ================================================
echo.
echo Diese Datei muss als Administrator ausgefuehrt werden!
echo.
pause

REM Prüfe ob bereits vorhanden
netsh advfirewall firewall show rule name="StockMaster Flask App" >nul 2>&1
if %errorlevel% equ 0 (
    echo Regel existiert bereits, loesche alte Regel...
    netsh advfirewall firewall delete rule name="StockMaster Flask App"
)

REM Füge neue Regel hinzu
echo Fuege Firewall-Regel hinzu...
netsh advfirewall firewall add rule name="StockMaster Flask App" dir=in action=allow protocol=TCP localport=5000 enable=yes

if %errorlevel% equ 0 (
    echo.
    echo ================================================
    echo OK Firewall-Regel erfolgreich hinzugefuegt!
    echo ================================================
    echo.
    echo Port 5000 ist jetzt von anderen Geraeten erreichbar.
    echo Sie koennen jetzt vom Handy auf die App zugreifen.
    echo.
    echo Ihre IP-Adresse: 192.168.178.99
    echo URL vom Handy: https://192.168.178.99:5000
    echo.
) else (
    echo.
    echo ================================================
    echo FEHLER: Firewall-Regel konnte nicht hinzugefuegt werden!
    echo ================================================
    echo.
    echo Bitte fuehren Sie diese Datei als Administrator aus:
    echo 1. Rechtsklick auf die Datei
    echo 2. "Als Administrator ausfuehren" waehlen
    echo.
)

pause
