"""
Automatischer Benachrichtigungs-Service

Überwacht das Lager und sendet automatische E-Mail-Benachrichtigungen:
- Niedriger Bestand (täglich)
- Wartungserinnerungen (täglich)
- Backup-Status (bei jedem Backup)
"""

import threading
import time
import schedule
import logging
import sqlite3
from datetime import datetime, timedelta
from email_service import get_email_service
import os

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self,
                 db_path='inventory.db',
                 check_interval_hours=24,
                 notification_email=None):
        """
        Initialisiert den Benachrichtigungs-Service

        Args:
            db_path: Pfad zur Datenbank
            check_interval_hours: Prüfintervall in Stunden
            notification_email: E-Mail-Adresse für Benachrichtigungen
        """
        self.db_path = db_path
        self.check_interval_hours = check_interval_hours
        self.notification_email = notification_email or os.getenv('NOTIFICATION_EMAIL')
        self.email_service = get_email_service()
        self.is_running = False
        self.thread = None

    def start(self):
        """Startet den Benachrichtigungs-Service"""
        if self.is_running:
            logger.warning("Benachrichtigungs-Service läuft bereits")
            return

        if not self.notification_email:
            logger.warning("Keine Benachrichtigungs-E-Mail konfiguriert - Service wird nicht gestartet")
            return

        logger.info(f"Starte Benachrichtigungs-Service (Intervall: {self.check_interval_hours}h)")
        logger.info(f"Benachrichtigungen gehen an: {self.notification_email}")

        # Erste Prüfung direkt beim Start
        self.check_and_notify()

        # Schedule einrichten
        schedule.every(self.check_interval_hours).hours.do(self.check_and_notify)

        # Thread starten
        self.is_running = True
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()

        logger.info("✓ Benachrichtigungs-Service gestartet")

    def stop(self):
        """Stoppt den Benachrichtigungs-Service"""
        logger.info("Stoppe Benachrichtigungs-Service...")
        self.is_running = False
        schedule.clear()

        if self.thread:
            self.thread.join(timeout=5)

        logger.info("✓ Benachrichtigungs-Service gestoppt")

    def _run_scheduler(self):
        """Interne Methode - führt den Scheduler aus"""
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Prüfe jede Minute
            except Exception as e:
                logger.error(f"Fehler im Scheduler: {e}")
                time.sleep(60)

    def get_low_stock_items(self):
        """Holt Artikel mit niedrigem Bestand"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT i.*,
                       c.name as category_name,
                       l.name as location_name
                FROM items i
                LEFT JOIN categories c ON i.category_id = c.id
                LEFT JOIN locations l ON i.location_id = l.id
                WHERE i.quantity <= i.min_quantity
                ORDER BY i.quantity ASC
            ''')

            items = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return items

        except Exception as e:
            logger.error(f"Fehler beim Abrufen von Artikeln mit niedrigem Bestand: {e}")
            return []

    def get_maintenance_due_items(self):
        """Holt Artikel mit fälliger Wartung"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Artikel, deren Wartung in den nächsten 7 Tagen fällig ist
            future_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')

            cursor.execute('''
                SELECT i.*,
                       c.name as category_name,
                       l.name as location_name
                FROM items i
                LEFT JOIN categories c ON i.category_id = c.id
                LEFT JOIN locations l ON i.location_id = l.id
                WHERE i.requires_maintenance = 1
                  AND i.next_maintenance_date IS NOT NULL
                  AND i.next_maintenance_date <= ?
                ORDER BY i.next_maintenance_date ASC
            ''', (future_date,))

            items = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return items

        except Exception as e:
            logger.error(f"Fehler beim Abrufen von Wartungsartikeln: {e}")
            return []

    def check_and_notify(self):
        """Prüft Lagerbestand und Wartungen, sendet Benachrichtigungen"""
        logger.info("Starte automatische Benachrichtigungsprüfung...")

        notifications_sent = 0

        # 1. Niedriger Bestand prüfen
        low_stock_items = self.get_low_stock_items()
        if low_stock_items:
            logger.info(f"Gefunden: {len(low_stock_items)} Artikel mit niedrigem Bestand")
            if self.email_service.send_low_stock_alert(self.notification_email, low_stock_items):
                notifications_sent += 1
                logger.info(f"✓ E-Mail für niedrigen Bestand gesendet ({len(low_stock_items)} Artikel)")
        else:
            logger.info("✓ Kein Artikel mit niedrigem Bestand gefunden")

        # 2. Wartungen prüfen
        maintenance_items = self.get_maintenance_due_items()
        if maintenance_items:
            logger.info(f"Gefunden: {len(maintenance_items)} Artikel mit fälliger Wartung")
            if self.email_service.send_maintenance_reminder(self.notification_email, maintenance_items):
                notifications_sent += 1
                logger.info(f"✓ Wartungserinnerung gesendet ({len(maintenance_items)} Artikel)")
        else:
            logger.info("✓ Keine fälligen Wartungen gefunden")

        logger.info(f"Benachrichtigungsprüfung abgeschlossen - {notifications_sent} E-Mail(s) gesendet")

    def notify_backup_status(self, success: bool, filename: str = None, error: str = None):
        """Sendet Backup-Benachrichtigung"""
        if not self.notification_email:
            return

        logger.info(f"Sende Backup-Benachrichtigung (Erfolg: {success})...")
        self.email_service.send_backup_notification(
            self.notification_email,
            success,
            filename,
            error
        )


# Globale Service-Instanz
_notification_service = None


def get_notification_service(db_path='inventory.db',
                             check_interval_hours=24,
                             notification_email=None):
    """Gibt die globale Benachrichtigungs-Service-Instanz zurück (Singleton)"""
    global _notification_service

    if _notification_service is None:
        _notification_service = NotificationService(
            db_path=db_path,
            check_interval_hours=check_interval_hours,
            notification_email=notification_email
        )

    return _notification_service


def main():
    """Test/Demo Funktion"""
    import signal
    import sys

    def signal_handler(sig, frame):
        print("\n\nStoppe Benachrichtigungs-Service...")
        service.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Service erstellen und starten
    service = get_notification_service(
        check_interval_hours=0.1,  # Alle 6 Minuten für Test
        notification_email='test@example.com'
    )
    service.start()

    print("\nBenachrichtigungs-Service läuft...")
    print("Drücke Ctrl+C zum Beenden\n")

    # Warte unendlich
    while True:
        time.sleep(1)


if __name__ == '__main__':
    main()
