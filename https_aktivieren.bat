@echo off
echo ================================================
echo HTTPS aktivieren
echo ================================================
echo.

if exist cert.pem.backup (
    ren cert.pem.backup cert.pem
    ren key.pem.backup key.pem
    echo OK HTTPS aktiviert
    echo.
    echo Server wird mit HTTPS starten
    echo Zugriff ueber: https://localhost:5000
    echo.
) else (
    echo Zertifikate bereits aktiv oder nicht vorhanden
    echo.
    if not exist cert.pem (
        echo Erstelle neue Zertifikate...
        python generate_cert.py
    )
)

echo ================================================
pause
