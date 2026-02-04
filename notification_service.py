"""
Automatischer Benachrichtigungs-Service

Überwacht das Lager und sendet automatische E-Mail-Benachrichtigungen:
- Wartungserinnerungen (täglich)
- Backup-Fehler (bei fehlgeschlagenem Backup)
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
            notification_email: Fallback E-Mail-Adresse (aus .env)
        """
        self.db_path = db_path
        self.check_interval_hours = check_interval_hours
        self.fallback_email = notification_email or os.getenv('NOTIFICATION_EMAIL')
        self.email_service = get_email_service()
        self.is_running = False
        self.thread = None

    def get_notification_recipients(self, notification_type):
        """
        Holt alle Benutzer die für einen bestimmten Benachrichtigungstyp angemeldet sind.

        Args:
            notification_type: 'low_stock', 'maintenance' oder 'backup'

        Returns:
            Liste von E-Mail-Adressen
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row

            column_map = {
                'maintenance': 'notify_maintenance',
                'backup': 'notify_backup'
            }

            column = column_map.get(notification_type)
            if not column:
                return [self.fallback_email] if self.fallback_email else []

            cursor = conn.cursor()
            cursor.execute(f'''
                SELECT DISTINCT email FROM users
                WHERE email IS NOT NULL AND email != '' AND {column} = 1
            ''')

            emails = [row['email'] for row in cursor.fetchall()]
            conn.close()

            # Fallback auf zentrale E-Mail wenn keine Benutzer-Emails vorhanden
            if not emails and self.fallback_email:
                return [self.fallback_email]

            return emails

        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Empfänger: {e}")
            return [self.fallback_email] if self.fallback_email else []

    def start(self):
        """Startet den Benachrichtigungs-Service"""
        if self.is_running:
            logger.warning("Benachrichtigungs-Service läuft bereits")
            return

        logger.info(f"Starte Benachrichtigungs-Service (Intervall: {self.check_interval_hours}h)")
        if self.fallback_email:
            logger.info(f"Fallback-E-Mail: {self.fallback_email}")
        logger.info("Benachrichtigungen werden an Benutzer mit hinterlegter E-Mail gesendet")

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

    def get_maintenance_due_items(self):
        """Holt Wartungen die fällig sind (aus item_maintenance_schedules)"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Wartungen, die in den nächsten 7 Tagen fällig sind
            future_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')

            # Versuche zuerst die neue Tabelle
            try:
                cursor.execute('''
                    SELECT ims.id as schedule_id, ims.interval_days, ims.next_date,
                           ims.priority,
                           i.name, i.sku,
                           mt.name as type_name, mt.color as type_color,
                           c.name as category_name,
                           l.name as location_name,
                           u.username as assigned_to,
                           ims.next_date as next_maintenance_date,
                           ims.interval_days as maintenance_interval_days
                    FROM item_maintenance_schedules ims
                    JOIN items i ON ims.item_id = i.id
                    JOIN maintenance_types mt ON ims.maintenance_type_id = mt.id
                    LEFT JOIN categories c ON i.category_id = c.id
                    LEFT JOIN locations l ON i.location_id = l.id
                    LEFT JOIN users u ON ims.assigned_user_id = u.id
                    WHERE ims.is_active = 1
                      AND ims.next_date IS NOT NULL
                      AND ims.next_date <= ?
                    ORDER BY ims.next_date ASC
                ''', (future_date,))
            except Exception:
                # Fallback auf alte Tabelle falls Migration noch nicht gelaufen
                cursor.execute('''
                    SELECT i.*, c.name as category_name, l.name as location_name
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
        """Prüft Wartungen und sendet Benachrichtigungen an alle aktivierten Benutzer"""
        logger.info("Starte automatische Benachrichtigungsprüfung...")

        notifications_sent = 0

        # Wartungen prüfen
        maintenance_items = self.get_maintenance_due_items()
        if maintenance_items:
            recipients = self.get_notification_recipients('maintenance')
            logger.info(f"Gefunden: {len(maintenance_items)} Artikel mit fälliger Wartung, {len(recipients)} Empfänger")
            for email in recipients:
                if self.email_service.send_maintenance_reminder(email, maintenance_items):
                    notifications_sent += 1
                    logger.info(f"✓ Wartungserinnerung gesendet an {email}")
        else:
            logger.info("✓ Keine fälligen Wartungen gefunden")

        logger.info(f"Benachrichtigungsprüfung abgeschlossen - {notifications_sent} E-Mail(s) gesendet")

    def notify_backup_status(self, success: bool, filename: str = None, error: str = None):
        """Sendet Backup-Fehler-Benachrichtigung an alle aktivierten Benutzer (nur bei Fehler)"""
        if success:
            logger.info("Backup erfolgreich - keine Fehler-Benachrichtigung nötig")
            return

        recipients = self.get_notification_recipients('backup')
        if not recipients:
            return

        logger.info(f"Sende Backup-Fehler-Benachrichtigung an {len(recipients)} Empfänger...")
        for email in recipients:
            self.email_service.send_backup_notification(
                email,
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
