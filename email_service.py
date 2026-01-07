"""
E-Mail-Benachrichtigungssystem für StockMaster

Sendet automatische E-Mail-Benachrichtigungen für:
- Niedriger Bestand
- Wartungserinnerungen
- Backup-Status
- Wichtige System-Events
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime
import os
from typing import List, Dict, Optional

# Logging konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self,
                 smtp_server: str = None,
                 smtp_port: int = None,
                 smtp_username: str = None,
                 smtp_password: str = None,
                 from_email: str = None,
                 from_name: str = "StockMaster"):
        """
        Initialisiert den E-Mail-Service

        Args:
            smtp_server: SMTP-Server (z.B. smtp.gmail.com)
            smtp_port: SMTP-Port (587 für TLS, 465 für SSL)
            smtp_username: SMTP-Benutzername
            smtp_password: SMTP-Passwort oder App-Passwort
            from_email: Absender E-Mail-Adresse
            from_name: Absender Name
        """
        self.smtp_server = smtp_server or os.getenv('SMTP_SERVER')
        self.smtp_port = smtp_port or int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = smtp_username or os.getenv('SMTP_USERNAME')
        self.smtp_password = smtp_password or os.getenv('SMTP_PASSWORD')
        self.from_email = from_email or os.getenv('SMTP_FROM_EMAIL', self.smtp_username)
        self.from_name = from_name
        self.use_tls = os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'

    def _create_message(self, to_email: str, subject: str, html_body: str, text_body: str = None) -> MIMEMultipart:
        """Erstellt eine E-Mail-Nachricht"""
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{self.from_name} <{self.from_email}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        msg['X-Mailer'] = 'StockMaster Email Service'

        # Text-Version (Fallback)
        if text_body:
            part1 = MIMEText(text_body, 'plain', 'utf-8')
            msg.attach(part1)

        # HTML-Version
        part2 = MIMEText(html_body, 'html', 'utf-8')
        msg.attach(part2)

        return msg

    def send_email(self, to_email: str, subject: str, html_body: str, text_body: str = None) -> bool:
        """
        Sendet eine E-Mail

        Returns:
            bool: True wenn erfolgreich, False bei Fehler
        """
        if not all([self.smtp_server, self.smtp_username, self.smtp_password]):
            logger.warning("E-Mail-Service nicht konfiguriert - E-Mail wird nicht gesendet")
            return False

        try:
            msg = self._create_message(to_email, subject, html_body, text_body)

            # Verbindung zum SMTP-Server
            if self.use_tls:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)

            server.login(self.smtp_username, self.smtp_password)
            server.send_message(msg)
            server.quit()

            logger.info(f"✓ E-Mail erfolgreich gesendet an {to_email}: {subject}")
            return True

        except Exception as e:
            logger.error(f"✗ Fehler beim E-Mail-Versand an {to_email}: {str(e)}")
            return False

    def send_low_stock_alert(self, to_email: str, items: List[Dict]) -> bool:
        """
        Sendet Warnung bei niedrigem Bestand

        Args:
            to_email: Empfänger E-Mail
            items: Liste der Artikel mit niedrigem Bestand
        """
        subject = f"⚠️ Niedriger Bestand - {len(items)} Artikel"

        # HTML-Template
        items_html = ""
        for item in items:
            items_html += f"""
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 12px; font-weight: 500;">{item['name']}</td>
                <td style="padding: 12px; color: #ef4444; font-weight: 600;">{item['quantity']} {item['unit']}</td>
                <td style="padding: 12px; color: #64748b;">{item['min_quantity']} {item['unit']}</td>
                <td style="padding: 12px;">{item.get('category_name', '-')}</td>
                <td style="padding: 12px;">{item.get('location_name', '-')}</td>
            </tr>
            """

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; color: #334155; margin: 0; padding: 0; background: #f8fafc;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #6366f1 0%, #ec4899 100%); padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
                    <h1 style="color: white; margin: 0; font-size: 28px;">⚠️ Niedriger Bestand</h1>
                    <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0;">StockMaster Benachrichtigung</p>
                </div>

                <div style="background: white; padding: 30px; border-radius: 0 0 12px 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <p style="font-size: 16px; color: #475569; margin-bottom: 20px;">
                        Es gibt <strong>{len(items)} Artikel</strong> mit niedrigem Bestand, die aufgefüllt werden sollten:
                    </p>

                    <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                        <thead>
                            <tr style="background: #f1f5f9; border-bottom: 2px solid #cbd5e1;">
                                <th style="padding: 12px; text-align: left; font-size: 12px; text-transform: uppercase; color: #64748b;">Artikel</th>
                                <th style="padding: 12px; text-align: left; font-size: 12px; text-transform: uppercase; color: #64748b;">Aktuell</th>
                                <th style="padding: 12px; text-align: left; font-size: 12px; text-transform: uppercase; color: #64748b;">Minimum</th>
                                <th style="padding: 12px; text-align: left; font-size: 12px; text-transform: uppercase; color: #64748b;">Kategorie</th>
                                <th style="padding: 12px; text-align: left; font-size: 12px; text-transform: uppercase; color: #64748b;">Standort</th>
                            </tr>
                        </thead>
                        <tbody>
                            {items_html}
                        </tbody>
                    </table>

                    <div style="margin-top: 30px; padding: 20px; background: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 6px;">
                        <p style="margin: 0; color: #92400e; font-weight: 500;">
                            💡 <strong>Tipp:</strong> Überprüfen Sie die Artikel und bestellen Sie rechtzeitig nach, um Lieferengpässe zu vermeiden.
                        </p>
                    </div>

                    <div style="margin-top: 30px; text-align: center;">
                        <a href="http://localhost:5000" style="display: inline-block; padding: 12px 30px; background: #6366f1; color: white; text-decoration: none; border-radius: 8px; font-weight: 600;">
                            Zur Lagerverwaltung
                        </a>
                    </div>
                </div>

                <div style="margin-top: 20px; text-align: center; color: #94a3b8; font-size: 12px;">
                    <p>StockMaster - Intelligente Lagerverwaltung</p>
                    <p>Automatische Benachrichtigung • {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_body = f"""
        NIEDRIGER BESTAND - {len(items)} ARTIKEL

        Die folgenden Artikel haben einen niedrigen Bestand:

        """
        for item in items:
            text_body += f"- {item['name']}: {item['quantity']} {item['unit']} (Min: {item['min_quantity']})\n"

        text_body += f"\n\nStockMaster - {datetime.now().strftime('%d.%m.%Y %H:%M')}"

        return self.send_email(to_email, subject, html_body, text_body)

    def send_maintenance_reminder(self, to_email: str, items: List[Dict]) -> bool:
        """
        Sendet Wartungserinnerung

        Args:
            to_email: Empfänger E-Mail
            items: Liste der Artikel mit fälliger Wartung
        """
        subject = f"🔧 Wartungserinnerung - {len(items)} Artikel"

        items_html = ""
        for item in items:
            next_date = item.get('next_maintenance_date', '-')
            items_html += f"""
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 12px; font-weight: 500;">{item['name']}</td>
                <td style="padding: 12px; color: #f59e0b; font-weight: 600;">{next_date}</td>
                <td style="padding: 12px; color: #64748b;">{item.get('maintenance_interval_days', '-')} Tage</td>
                <td style="padding: 12px;">{item.get('location_name', '-')}</td>
            </tr>
            """

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; color: #334155; margin: 0; padding: 0; background: #f8fafc;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #f59e0b 0%, #ef4444 100%); padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
                    <h1 style="color: white; margin: 0; font-size: 28px;">🔧 Wartungserinnerung</h1>
                    <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0;">Wartungsarbeiten erforderlich</p>
                </div>

                <div style="background: white; padding: 30px; border-radius: 0 0 12px 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <p style="font-size: 16px; color: #475569; margin-bottom: 20px;">
                        Die Wartung für <strong>{len(items)} Artikel</strong> ist fällig oder steht bevor:
                    </p>

                    <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                        <thead>
                            <tr style="background: #f1f5f9; border-bottom: 2px solid #cbd5e1;">
                                <th style="padding: 12px; text-align: left; font-size: 12px; text-transform: uppercase; color: #64748b;">Artikel</th>
                                <th style="padding: 12px; text-align: left; font-size: 12px; text-transform: uppercase; color: #64748b;">Nächste Wartung</th>
                                <th style="padding: 12px; text-align: left; font-size: 12px; text-transform: uppercase; color: #64748b;">Intervall</th>
                                <th style="padding: 12px; text-align: left; font-size: 12px; text-transform: uppercase; color: #64748b;">Standort</th>
                            </tr>
                        </thead>
                        <tbody>
                            {items_html}
                        </tbody>
                    </table>

                    <div style="margin-top: 30px; padding: 20px; background: #fee2e2; border-left: 4px solid #ef4444; border-radius: 6px;">
                        <p style="margin: 0; color: #991b1b; font-weight: 500;">
                            ⚠️ <strong>Wichtig:</strong> Planen Sie die Wartungsarbeiten rechtzeitig ein, um Ausfälle zu vermeiden.
                        </p>
                    </div>

                    <div style="margin-top: 30px; text-align: center;">
                        <a href="http://localhost:5000" style="display: inline-block; padding: 12px 30px; background: #6366f1; color: white; text-decoration: none; border-radius: 8px; font-weight: 600;">
                            Zur Lagerverwaltung
                        </a>
                    </div>
                </div>

                <div style="margin-top: 20px; text-align: center; color: #94a3b8; font-size: 12px;">
                    <p>StockMaster - Intelligente Lagerverwaltung</p>
                    <p>Automatische Benachrichtigung • {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_body = f"""
        WARTUNGSERINNERUNG - {len(items)} ARTIKEL

        Die folgenden Artikel benötigen eine Wartung:

        """
        for item in items:
            text_body += f"- {item['name']}: Nächste Wartung am {item.get('next_maintenance_date', '-')}\n"

        text_body += f"\n\nStockMaster - {datetime.now().strftime('%d.%m.%Y %H:%M')}"

        return self.send_email(to_email, subject, html_body, text_body)

    def send_backup_notification(self, to_email: str, success: bool, filename: str = None, error: str = None) -> bool:
        """Sendet Backup-Benachrichtigung"""
        if success:
            subject = "✓ Backup erfolgreich erstellt"
            color = "#22c55e"
            icon = "✓"
            message = f"Das automatische Backup wurde erfolgreich erstellt: {filename}"
        else:
            subject = "✗ Backup fehlgeschlagen"
            color = "#ef4444"
            icon = "✗"
            message = f"Das automatische Backup ist fehlgeschlagen: {error}"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: sans-serif; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; border: 2px solid {color}; border-radius: 8px; padding: 20px;">
                <h2 style="color: {color}; margin-top: 0;">{icon} Backup-Benachrichtigung</h2>
                <p>{message}</p>
                <p style="color: #666; font-size: 12px; margin-top: 20px;">
                    StockMaster - {datetime.now().strftime('%d.%m.%Y %H:%M')}
                </p>
            </div>
        </body>
        </html>
        """

        return self.send_email(to_email, subject, html_body)


# Globale Service-Instanz
_email_service = None


def get_email_service() -> EmailService:
    """Gibt die globale E-Mail-Service-Instanz zurück (Singleton)"""
    global _email_service

    if _email_service is None:
        _email_service = EmailService()

    return _email_service


def main():
    """Test-Funktion"""
    service = get_email_service()

    # Test: Niedriger Bestand
    test_items = [
        {
            'name': 'Schrauben M8',
            'quantity': 5,
            'unit': 'Stück',
            'min_quantity': 50,
            'category_name': 'Kleinteile',
            'location_name': 'Regal A1'
        },
        {
            'name': 'Kabelbinder',
            'quantity': 12,
            'unit': 'Pack',
            'min_quantity': 20,
            'category_name': 'Elektro',
            'location_name': 'Lager 2'
        }
    ]

    result = service.send_low_stock_alert('test@example.com', test_items)
    print(f"E-Mail gesendet: {result}")


if __name__ == '__main__':
    main()
