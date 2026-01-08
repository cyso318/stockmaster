"""
Google Drive Synchronisation für StockMaster
Backup der SQLite-Datenbank zu Google Drive
"""

import os
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from datetime import datetime
import shutil

# Google Drive API Scopes
SCOPES = ['https://www.googleapis.com/auth/drive.file']

class GoogleDriveSync:
    def __init__(self, db_path='inventory.db'):
        self.db_path = db_path
        self.creds = None
        self.service = None
        self.folder_id = None

    def authenticate(self):
        """Authentifiziert mit Google Drive API"""
        # Token-Datei existiert bereits?
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                self.creds = pickle.load(token)

        # Wenn keine gültigen Credentials, neu authentifizieren
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                if not os.path.exists('credentials.json'):
                    raise FileNotFoundError(
                        'credentials.json nicht gefunden! '
                        'Bitte laden Sie die OAuth 2.0 Credentials von der Google Cloud Console herunter.'
                    )

                # Versuche Browser-Authentifizierung (nur auf lokalem PC)
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        'credentials.json', SCOPES)
                    self.creds = flow.run_local_server(port=0)
                except Exception as e:
                    # Auf Server ohne Browser: Token muss manuell erstellt werden
                    raise RuntimeError(
                        'Google Drive Authentifizierung fehlgeschlagen. '
                        'Bitte authentifizieren Sie auf einem lokalen PC mit Browser und laden Sie token.pickle hoch. '
                        f'Fehler: {str(e)}'
                    )

            # Speichere Credentials für nächstes Mal
            with open('token.pickle', 'wb') as token:
                pickle.dump(self.creds, token)

        self.service = build('drive', 'v3', credentials=self.creds)
        return True

    def get_or_create_folder(self, folder_name='StockMaster Backups'):
        """Erstellt oder findet den Backup-Ordner auf Google Drive"""
        if not self.service:
            self.authenticate()

        # Suche nach existierendem Ordner
        results = self.service.files().list(
            q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            spaces='drive',
            fields='files(id, name)'
        ).execute()

        items = results.get('files', [])

        if items:
            self.folder_id = items[0]['id']
            return self.folder_id

        # Ordner existiert nicht, erstelle neuen
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }

        folder = self.service.files().create(
            body=file_metadata,
            fields='id'
        ).execute()

        self.folder_id = folder.get('id')
        return self.folder_id

    def upload_database(self, db_path=None):
        """Lädt die Datenbank zu Google Drive hoch"""
        if not self.service:
            self.authenticate()

        # Verwende self.db_path wenn kein db_path übergeben wurde
        if db_path is None:
            db_path = self.db_path

        if not os.path.exists(db_path):
            raise FileNotFoundError(f'Datenbank {db_path} nicht gefunden!')

        # Stelle sicher, dass Backup-Ordner existiert
        if not self.folder_id:
            self.get_or_create_folder()

        # Erstelle Backup mit Zeitstempel
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f'inventory_backup_{timestamp}.db'

        file_metadata = {
            'name': backup_name,
            'parents': [self.folder_id]
        }

        media = MediaFileUpload(db_path, mimetype='application/x-sqlite3', resumable=True)

        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink'
        ).execute()

        return {
            'file_id': file.get('id'),
            'name': file.get('name'),
            'link': file.get('webViewLink'),
            'timestamp': timestamp
        }

    def list_backups(self, limit=10):
        """Listet die letzten Backups auf Google Drive"""
        if not self.service:
            self.authenticate()

        if not self.folder_id:
            self.get_or_create_folder()

        results = self.service.files().list(
            q=f"'{self.folder_id}' in parents and trashed=false",
            pageSize=limit,
            orderBy='createdTime desc',
            fields='files(id, name, createdTime, size, webViewLink)'
        ).execute()

        items = results.get('files', [])
        return items

    def download_backup(self, file_id, destination='inventory_restored.db'):
        """Lädt ein Backup von Google Drive herunter"""
        if not self.service:
            self.authenticate()

        request = self.service.files().get_media(fileId=file_id)

        with open(destination, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()

        return destination

    def delete_old_backups(self, keep_count=5):
        """Löscht alte Backups, behält nur die letzten N"""
        if not self.service:
            self.authenticate()

        if not self.folder_id:
            self.get_or_create_folder()

        backups = self.list_backups(limit=100)

        if len(backups) <= keep_count:
            return {'deleted': 0, 'kept': len(backups)}

        # Lösche alle außer den neuesten keep_count
        to_delete = backups[keep_count:]
        deleted_count = 0

        for backup in to_delete:
            try:
                self.service.files().delete(fileId=backup['id']).execute()
                deleted_count += 1
            except Exception as e:
                print(f"Fehler beim Löschen von {backup['name']}: {e}")

        return {'deleted': deleted_count, 'kept': keep_count}

    def get_sync_status(self):
        """Gibt den Status der letzten Synchronisation zurück"""
        try:
            if not self.service:
                self.authenticate()

            backups = self.list_backups(limit=1)

            if backups:
                last_backup = backups[0]
                return {
                    'status': 'success',
                    'last_sync': last_backup['createdTime'],
                    'last_backup_name': last_backup['name'],
                    'last_backup_size': last_backup.get('size', 0)
                }
            else:
                return {
                    'status': 'no_backups',
                    'message': 'Keine Backups gefunden'
                }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }

# Test-Funktion
if __name__ == '__main__':
    print("=== Google Drive Sync Test ===\n")

    sync = GoogleDriveSync()

    try:
        print("1. Authentifiziere mit Google Drive...")
        sync.authenticate()
        print("✓ Authentifizierung erfolgreich\n")

        print("2. Erstelle/Finde Backup-Ordner...")
        folder_id = sync.get_or_create_folder()
        print(f"✓ Ordner-ID: {folder_id}\n")

        print("3. Liste vorhandene Backups...")
        backups = sync.list_backups()
        if backups:
            print(f"✓ {len(backups)} Backups gefunden:")
            for backup in backups:
                print(f"  - {backup['name']} ({backup['createdTime']})")
        else:
            print("  Keine Backups vorhanden")
        print()

        if os.path.exists('inventory.db'):
            print("4. Lade Datenbank hoch...")
            result = sync.upload_database()
            print(f"✓ Upload erfolgreich: {result['name']}")
            print(f"  Link: {result['link']}\n")
        else:
            print("4. Überspringe Upload (keine Datenbank gefunden)\n")

        print("=== Test erfolgreich abgeschlossen ===")

    except FileNotFoundError as e:
        print(f"❌ Fehler: {e}")
        print("\nBitte stelle sicher, dass credentials.json existiert!")
    except Exception as e:
        print(f"❌ Fehler: {e}")
