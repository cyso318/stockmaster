@echo off
echo ================================================
echo HTTPS deaktivieren
echo ================================================
echo.

if exist cert.pem (
    ren cert.pem cert.pem.backup
    ren key.pem key.pem.backup
    echo OK HTTPS deaktiviert
    echo.
    echo Server wird mit HTTP starten
    echo Zugriff ueber: http://localhost:5000
    echo.
    echo HINWEIS: Kamera funktioniert nur auf localhost
    echo Vom Handy wird die Kamera NICHT funktionieren!
    echo.
) else (
    echo HTTPS bereits deaktiviert
    echo.
)

echo ================================================
pause
