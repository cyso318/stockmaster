"""
Automatisches Backup-System für die Lagerverwaltung

Dieses Modul führt automatisch regelmäßige Backups zur Google Drive durch
und verwaltet die Backup-Historie.
"""

import threading
import time
import schedule
import logging
from datetime import datetime
from gdrive_sync import GoogleDriveSync

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AutoBackupService:
    def __init__(self, db_path='inventory.db', backup_interval_hours=24, keep_backups=30):
        """
        Initialisiert den Auto-Backup-Service

        Args:
            db_path: Pfad zur Datenbank
            backup_interval_hours: Intervall zwischen Backups in Stunden
            keep_backups: Anzahl der zu behaltenden Backups
        """
        self.db_path = db_path
        self.backup_interval_hours = backup_interval_hours
        self.keep_backups = keep_backups
        self.sync = GoogleDriveSync(db_path=db_path)
        self.is_running = False
        self.thread = None
        self.last_backup_time = None
        self.last_backup_status = None
        self.backup_count = 0

    def start(self):
        """Startet den automatischen Backup-Service"""
        if self.is_running:
            logger.warning("Backup-Service läuft bereits")
            return

        logger.info(f"Starte automatischen Backup-Service (Intervall: {self.backup_interval_hours}h)")

        # Authentifizierung beim Start
        try:
            self.sync.authenticate()
            self.sync.get_or_create_folder()
            logger.info("✓ Google Drive Verbindung hergestellt")

            # Erstes Backup direkt beim Start
            self.perform_backup()

        except Exception as e:
            logger.error(f"Fehler bei der Initialisierung: {e}")
            logger.warning("Backup-Service wird trotzdem gestartet - spätere Backups könnten funktionieren")

        # Schedule einrichten
        schedule.every(self.backup_interval_hours).hours.do(self.perform_backup)

        # Thread starten
        self.is_running = True
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()

        logger.info("✓ Automatischer Backup-Service gestartet")

    def stop(self):
        """Stoppt den automatischen Backup-Service"""
        logger.info("Stoppe automatischen Backup-Service...")
        self.is_running = False
        schedule.clear()

        if self.thread:
            self.thread.join(timeout=5)

        logger.info("✓ Backup-Service gestoppt")

    def _run_scheduler(self):
        """Interne Methode - führt den Scheduler aus"""
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Prüfe jede Minute
            except Exception as e:
                logger.error(f"Fehler im Scheduler: {e}")
                time.sleep(60)

    def perform_backup(self):
        """Führt ein Backup durch"""
        logger.info("Starte automatisches Backup...")

        try:
            # Backup durchführen
            result = self.sync.upload_database()

            if result:
                self.last_backup_time = datetime.now()
                self.last_backup_status = 'success'
                self.backup_count += 1

                logger.info(f"✓ Backup #{self.backup_count} erfolgreich abgeschlossen")
                logger.info(f"  Datei: {result.get('name')}")
                logger.info(f"  Link: {result.get('link')}")

                # Alte Backups aufräumen
                try:
                    cleanup_result = self.sync.delete_old_backups(keep_count=self.keep_backups)
                    logger.info(f"  Aufgeräumt: {cleanup_result['deleted']} alte Backups gelöscht")
                except Exception as e:
                    logger.warning(f"Fehler beim Aufräumen alter Backups: {e}")

                return {
                    'success': True,
                    'filename': result.get('name'),
                    'link': result.get('link'),
                    'file_id': result.get('file_id')
                }
            else:
                self.last_backup_status = 'failed'
                logger.error(f"✗ Backup fehlgeschlagen")
                return {
                    'success': False,
                    'error': 'Upload fehlgeschlagen'
                }

        except Exception as e:
            self.last_backup_status = 'failed'
            logger.error(f"✗ Backup-Fehler: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_status(self):
        """Gibt den aktuellen Status des Backup-Services zurück"""
        next_backup = None
        if self.is_running and self.last_backup_time:
            from datetime import timedelta
            next_backup = self.last_backup_time + timedelta(hours=self.backup_interval_hours)

        return {
            'is_running': self.is_running,
            'backup_interval_hours': self.backup_interval_hours,
            'last_backup_time': self.last_backup_time.isoformat() if self.last_backup_time else None,
            'last_backup_status': self.last_backup_status,
            'next_backup_time': next_backup.isoformat() if next_backup else None,
            'backup_count': self.backup_count,
            'keep_backups': self.keep_backups
        }

    def manual_backup(self):
        """Führt ein manuelles Backup durch (außerhalb des Schedules)"""
        logger.info("Manuelles Backup angefordert...")
        return self.perform_backup()


# Globale Service-Instanz
_backup_service = None


def get_backup_service(db_path='inventory.db', backup_interval_hours=24, keep_backups=30):
    """Gibt die globale Backup-Service-Instanz zurück (Singleton)"""
    global _backup_service

    if _backup_service is None:
        _backup_service = AutoBackupService(
            db_path=db_path,
            backup_interval_hours=backup_interval_hours,
            keep_backups=keep_backups
        )

    return _backup_service


def main():
    """Test/Demo Funktion"""
    import signal
    import sys

    def signal_handler(sig, frame):
        print("\n\nStoppe Backup-Service...")
        service.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Service erstellen und starten
    service = get_backup_service(backup_interval_hours=0.1)  # Alle 6 Minuten für Test
    service.start()

    print("\nAuto-Backup-Service läuft...")
    print("Drücke Ctrl+C zum Beenden\n")

    # Warte unendlich
    while True:
        time.sleep(1)


if __name__ == '__main__':
    main()
