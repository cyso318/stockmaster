from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, Response
from werkzeug.middleware.proxy_fix import ProxyFix
import sqlite3
import os
import json
from datetime import datetime, timedelta
import threading
import time
import qrcode
import barcode
from barcode.writer import ImageWriter
from io import BytesIO
import base64
from functools import wraps
import secrets
import bcrypt
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_wtf.csrf import CSRFProtect
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm

# Lade Umgebungsvariablen
load_dotenv()

app = Flask(__name__)

# Proxy-Fix für korrekte Session-Cookies hinter Reverse-Proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Sicherheitskonfiguration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=int(os.getenv('SESSION_TIMEOUT_MINUTES', '30')))  # 30 Min Session-Timeout
app.config['SESSION_COOKIE_HTTPONLY'] = os.getenv('SESSION_COOKIE_HTTPONLY', 'True') == 'True'

# SESSION_COOKIE_SAMESITE behandeln (None als String kommt aus .env)
samesite_value = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
app.config['SESSION_COOKIE_SAMESITE'] = None if samesite_value == 'None' else samesite_value

app.config['SESSION_COOKIE_SECURE'] = os.getenv('SESSION_COOKIE_SECURE', 'False') == 'True'  # Für HTTPS
app.config['SESSION_COOKIE_NAME'] = 'session'  # Einfacher Name
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max file upload

# Rate Limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[os.getenv('API_RATE_LIMIT', '100 per minute')],
    storage_uri=os.getenv('RATELIMIT_STORAGE_URL', 'memory://')
)

# CSRF-Schutz
csrf = CSRFProtect(app)
app.config['WTF_CSRF_CHECK_DEFAULT'] = False  # Wir kontrollieren CSRF manuell
app.config['WTF_CSRF_HEADERS'] = ['X-CSRFToken']

# Jinja2 Filter für JSON parsing
@app.template_filter('fromjson')
def fromjson_filter(value):
    """Parse JSON string to Python object"""
    if isinstance(value, str):
        return json.loads(value)
    return value

# Security Headers
if os.getenv('SESSION_COOKIE_SECURE', 'False') == 'True':
    # Produktion mit HTTPS
    Talisman(app,
             force_https=True,
             strict_transport_security=True,
             strict_transport_security_max_age=31536000,
             content_security_policy={
                 'default-src': "'self'",
                 'script-src': "'self' 'unsafe-inline' https://cdn.jsdelivr.net",
                 'style-src': "'self' 'unsafe-inline'",
                 'img-src': "'self' data:",
                 'font-src': "'self'",
                 'connect-src': "'self'",
                 'frame-ancestors': "'none'",
             },
             content_security_policy_nonce_in=['script-src'],
             feature_policy={
                 'geolocation': "'none'",
                 'camera': "'none'",
                 'microphone': "'none'",
             })
else:
    # Entwicklung - Basis Security Headers ohne HTTPS
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

# Datenbank Pfad
DB_PATH = 'inventory.db'
BACKUP_FOLDER = 'backups'
UPLOAD_FOLDER = 'static/uploads/items'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Erstelle Upload-Ordner falls nicht vorhanden
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Google Drive Sync Status
sync_status = {
    'last_sync': None,
    'status': 'Nicht konfiguriert',
    'auto_sync_enabled': False
}

# Account Locking - Schutz vor Brute-Force
failed_login_attempts = {}  # IP → {'count': int, 'locked_until': datetime}
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)

def login_required(f):
    """Decorator für geschützte Routen"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator für Admin-only Routen"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        if not session.get('is_admin'):
            return jsonify({'success': False, 'message': 'Admin-Rechte erforderlich'}), 403
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    """Prüft ob Datei-Extension erlaubt ist"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_password(password):
    """
    Validiert Passwort-Stärke
    Mindestens 8 Zeichen, 1 Großbuchstabe, 1 Kleinbuchstabe, 1 Zahl
    """
    if len(password) < 8:
        return False, "Passwort muss mindestens 8 Zeichen lang sein"
    if not any(c.isupper() for c in password):
        return False, "Passwort muss mindestens einen Großbuchstaben enthalten"
    if not any(c.islower() for c in password):
        return False, "Passwort muss mindestens einen Kleinbuchstaben enthalten"
    if not any(c.isdigit() for c in password):
        return False, "Passwort muss mindestens eine Zahl enthalten"
    return True, "OK"

def is_account_locked(ip_address):
    """Prüft ob Account gesperrt ist"""
    if ip_address in failed_login_attempts:
        attempt_data = failed_login_attempts[ip_address]
        if 'locked_until' in attempt_data and attempt_data['locked_until'] > datetime.now():
            return True, attempt_data['locked_until']
    return False, None

def record_failed_login(ip_address):
    """Registriert fehlgeschlagenen Login-Versuch"""
    if ip_address not in failed_login_attempts:
        failed_login_attempts[ip_address] = {'count': 0}

    failed_login_attempts[ip_address]['count'] += 1

    if failed_login_attempts[ip_address]['count'] >= MAX_LOGIN_ATTEMPTS:
        failed_login_attempts[ip_address]['locked_until'] = datetime.now() + LOCKOUT_DURATION
        return True  # Account wurde gesperrt

    return False  # Noch nicht gesperrt

def reset_failed_logins(ip_address):
    """Setzt fehlgeschlagene Login-Versuche zurück"""
    if ip_address in failed_login_attempts:
        del failed_login_attempts[ip_address]

def init_db():
    """Initialisiert die Datenbank mit den notwendigen Tabellen"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Organisationen Tabelle
    c.execute('''CREATE TABLE IF NOT EXISTS organizations
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL UNIQUE,
                  slug TEXT NOT NULL UNIQUE,
                  email TEXT NOT NULL,
                  phone TEXT,
                  address TEXT,
                  plan TEXT DEFAULT 'free',
                  max_users INTEGER DEFAULT 5,
                  max_items INTEGER DEFAULT 1000,
                  is_active BOOLEAN DEFAULT 1,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # Einladungstokens Tabelle
    c.execute('''CREATE TABLE IF NOT EXISTS invitation_tokens
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  organization_id INTEGER NOT NULL,
                  token TEXT NOT NULL UNIQUE,
                  created_by INTEGER NOT NULL,
                  is_used BOOLEAN DEFAULT 0,
                  used_by INTEGER,
                  expires_at TIMESTAMP,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  used_at TIMESTAMP,
                  FOREIGN KEY (organization_id) REFERENCES organizations (id),
                  FOREIGN KEY (created_by) REFERENCES users (id),
                  FOREIGN KEY (used_by) REFERENCES users (id))''')

    # Benutzer Tabelle (mit organization_id)
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  organization_id INTEGER NOT NULL,
                  username TEXT NOT NULL,
                  password_hash TEXT NOT NULL,
                  email TEXT,
                  first_name TEXT,
                  last_name TEXT,
                  is_admin BOOLEAN DEFAULT 0,
                  is_org_owner BOOLEAN DEFAULT 0,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  last_login TIMESTAMP,
                  FOREIGN KEY (organization_id) REFERENCES organizations (id),
                  UNIQUE(organization_id, username))''')

    # Kategorien Tabelle (mit organization_id)
    c.execute('''CREATE TABLE IF NOT EXISTS categories
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  organization_id INTEGER NOT NULL,
                  name TEXT NOT NULL,
                  description TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (organization_id) REFERENCES organizations (id),
                  UNIQUE(organization_id, name))''')

    # Standorte Tabelle (mit organization_id)
    c.execute('''CREATE TABLE IF NOT EXISTS locations
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  organization_id INTEGER NOT NULL,
                  name TEXT NOT NULL,
                  description TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (organization_id) REFERENCES organizations (id),
                  UNIQUE(organization_id, name))''')

    # Artikel Tabelle (mit organization_id)
    c.execute('''CREATE TABLE IF NOT EXISTS items
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  organization_id INTEGER NOT NULL,
                  sku TEXT,
                  name TEXT NOT NULL,
                  description TEXT,
                  category_id INTEGER,
                  location_id INTEGER,
                  quantity INTEGER DEFAULT 0,
                  min_quantity INTEGER DEFAULT 0,
                  unit TEXT DEFAULT 'Stück',
                  price REAL DEFAULT 0.0,
                  supplier TEXT,
                  notes TEXT,
                  requires_maintenance BOOLEAN DEFAULT 0,
                  maintenance_interval_days INTEGER,
                  last_maintenance_date DATE,
                  next_maintenance_date DATE,
                  maintenance_notes TEXT,
                  image_path TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (organization_id) REFERENCES organizations (id),
                  FOREIGN KEY (category_id) REFERENCES categories (id),
                  FOREIGN KEY (location_id) REFERENCES locations (id),
                  UNIQUE(organization_id, sku))''')

    # Migration: Barcode-Feld hinzufügen (falls noch nicht vorhanden)
    try:
        c.execute("ALTER TABLE items ADD COLUMN barcode TEXT")
        print("✓ Barcode-Feld zur Items-Tabelle hinzugefügt")
    except:
        pass  # Spalte existiert bereits

    # Migration: Gruppen-Felder hinzufügen
    try:
        c.execute("ALTER TABLE items ADD COLUMN is_group BOOLEAN DEFAULT 0")
        print("✓ Gruppen-Feld (is_group) zur Items-Tabelle hinzugefügt")
    except:
        pass  # Spalte existiert bereits

    try:
        c.execute("ALTER TABLE items ADD COLUMN group_id INTEGER REFERENCES items(id)")
        print("✓ Gruppen-Zuordnung (group_id) zur Items-Tabelle hinzugefügt")
    except:
        pass  # Spalte existiert bereits

    # Bewegungen Tabelle (Ein-/Ausbuchungen)
    c.execute('''CREATE TABLE IF NOT EXISTS movements
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  item_id INTEGER NOT NULL,
                  user_id INTEGER,
                  type TEXT NOT NULL,
                  quantity INTEGER NOT NULL,
                  reference TEXT,
                  notes TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (item_id) REFERENCES items (id),
                  FOREIGN KEY (user_id) REFERENCES users (id))''')

    # Sync Log Tabelle
    c.execute('''CREATE TABLE IF NOT EXISTS sync_log
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  organization_id INTEGER,
                  sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  status TEXT,
                  message TEXT,
                  FOREIGN KEY (organization_id) REFERENCES organizations (id))''')

    # Wartungshistorie Tabelle
    c.execute('''CREATE TABLE IF NOT EXISTS maintenance_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  item_id INTEGER NOT NULL,
                  user_id INTEGER,
                  maintenance_date DATE NOT NULL,
                  performed_by TEXT,
                  notes TEXT,
                  next_maintenance_date DATE,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (item_id) REFERENCES items (id),
                  FOREIGN KEY (user_id) REFERENCES users (id))''')

    # Wartungstypen Tabelle
    c.execute('''CREATE TABLE IF NOT EXISTS maintenance_types
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  organization_id INTEGER NOT NULL,
                  name TEXT NOT NULL,
                  description TEXT,
                  color TEXT DEFAULT '#6366f1',
                  icon TEXT DEFAULT 'wrench',
                  default_interval_days INTEGER,
                  is_active BOOLEAN DEFAULT 1,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (organization_id) REFERENCES organizations (id),
                  UNIQUE(organization_id, name))''')

    # Wartungspläne pro Artikel (ersetzt alte Einzelfelder auf items)
    c.execute('''CREATE TABLE IF NOT EXISTS item_maintenance_schedules
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  item_id INTEGER NOT NULL,
                  maintenance_type_id INTEGER NOT NULL,
                  interval_days INTEGER NOT NULL,
                  last_date DATE,
                  next_date DATE,
                  assigned_user_id INTEGER,
                  is_active BOOLEAN DEFAULT 1,
                  priority TEXT DEFAULT 'normal',
                  notes TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE CASCADE,
                  FOREIGN KEY (maintenance_type_id) REFERENCES maintenance_types (id),
                  FOREIGN KEY (assigned_user_id) REFERENCES users (id),
                  UNIQUE(item_id, maintenance_type_id))''')

    # Wartungs-Checklisten pro Typ
    c.execute('''CREATE TABLE IF NOT EXISTS maintenance_checklists
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  maintenance_type_id INTEGER NOT NULL,
                  organization_id INTEGER NOT NULL,
                  name TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (maintenance_type_id) REFERENCES maintenance_types (id) ON DELETE CASCADE,
                  FOREIGN KEY (organization_id) REFERENCES organizations (id))''')

    # Checklisten-Prüfpunkte
    c.execute('''CREATE TABLE IF NOT EXISTS checklist_items
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  checklist_id INTEGER NOT NULL,
                  description TEXT NOT NULL,
                  sort_order INTEGER DEFAULT 0,
                  is_required BOOLEAN DEFAULT 0,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (checklist_id) REFERENCES maintenance_checklists (id) ON DELETE CASCADE)''')

    # Checklisten-Ergebnisse bei Wartungsabschluss
    c.execute('''CREATE TABLE IF NOT EXISTS maintenance_checklist_results
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  maintenance_history_id INTEGER NOT NULL,
                  checklist_item_id INTEGER NOT NULL,
                  is_checked BOOLEAN DEFAULT 0,
                  notes TEXT,
                  FOREIGN KEY (maintenance_history_id) REFERENCES maintenance_history (id) ON DELETE CASCADE,
                  FOREIGN KEY (checklist_item_id) REFERENCES checklist_items (id))''')

    # Label Templates Tabelle
    c.execute('''CREATE TABLE IF NOT EXISTS label_templates
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  organization_id INTEGER NOT NULL,
                  name TEXT NOT NULL,
                  description TEXT,
                  width_mm REAL DEFAULT 62,
                  height_mm REAL DEFAULT 42,
                  layout_config TEXT NOT NULL,
                  is_default BOOLEAN DEFAULT 0,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (organization_id) REFERENCES organizations (id))''')

    # Entnahmescheine Tabelle
    c.execute('''CREATE TABLE IF NOT EXISTS withdrawal_slips
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  organization_id INTEGER NOT NULL,
                  user_id INTEGER,
                  reference TEXT,
                  notes TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (organization_id) REFERENCES organizations (id),
                  FOREIGN KEY (user_id) REFERENCES users (id))''')

    conn.commit()

    # Migration: slip_id Feld zu movements hinzufügen
    try:
        c.execute("ALTER TABLE movements ADD COLUMN slip_id INTEGER REFERENCES withdrawal_slips(id)")
    except:
        pass

    # Migrationen: Erweitere maintenance_history um neue Felder
    for col_statement in [
        "ALTER TABLE maintenance_history ADD COLUMN maintenance_type_id INTEGER REFERENCES maintenance_types(id)",
        "ALTER TABLE maintenance_history ADD COLUMN schedule_id INTEGER REFERENCES item_maintenance_schedules(id)",
        "ALTER TABLE maintenance_history ADD COLUMN cost REAL DEFAULT 0",
        "ALTER TABLE maintenance_history ADD COLUMN cost_parts REAL DEFAULT 0",
        "ALTER TABLE maintenance_history ADD COLUMN cost_labor REAL DEFAULT 0",
        "ALTER TABLE maintenance_history ADD COLUMN cost_notes TEXT",
        "ALTER TABLE maintenance_history ADD COLUMN organization_id INTEGER REFERENCES organizations(id)",
    ]:
        try:
            c.execute(col_statement)
        except:
            pass

    # Migrationen: Füge image_path Feld hinzu falls nicht vorhanden
    try:
        # Prüfe ob image_path bereits existiert
        cursor = conn.execute("PRAGMA table_info(items)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'image_path' not in columns:
            print("Führe Migration aus: Füge image_path Feld zu items Tabelle hinzu...")
            conn.execute('ALTER TABLE items ADD COLUMN image_path TEXT')
            conn.commit()
            print("OK: image_path Feld hinzugefügt")
    except Exception as e:
        print(f"Info: Migration image_path - {e}")

    # Migration: Benachrichtigungs-Einstellungen pro Benutzer
    for col_statement in [
        "ALTER TABLE users ADD COLUMN notify_low_stock BOOLEAN DEFAULT 1",
        "ALTER TABLE users ADD COLUMN notify_maintenance BOOLEAN DEFAULT 1",
        "ALTER TABLE users ADD COLUMN notify_backup BOOLEAN DEFAULT 0",
    ]:
        try:
            c.execute(col_statement)
        except:
            pass

    # Erstelle Standard-Organisation und Admin-Benutzer falls nicht vorhanden
    try:
        # Prüfe ob bereits Organisationen existieren
        org_count = conn.execute('SELECT COUNT(*) as count FROM organizations').fetchone()['count']

        if org_count == 0:
            print("\n" + "="*60)
            print("Erstelle Standard-Organisation und Admin-Benutzer...")
            print("="*60)

            # Erstelle Standard-Organisation
            cursor = conn.execute('''
                INSERT INTO organizations (name, slug, email, phone, plan, max_users, max_items)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('Standard Organisation', 'standard-organisation', '', '', 'free', 5, 1000))

            org_id = cursor.lastrowid

            # Erstelle Admin-Benutzer
            admin_password_hash = hash_password('admin123')
            conn.execute('''
                INSERT INTO users (organization_id, username, password_hash, email, first_name, last_name, is_admin, is_org_owner)
                VALUES (?, ?, ?, ?, ?, ?, 1, 1)
            ''', (org_id, 'admin', admin_password_hash, 'admin@example.com', 'Admin', 'User'))

            conn.commit()

            print("OK: Standard-Organisation erstellt (ID: {})".format(org_id))
            print("OK: Admin-Benutzer erstellt")
            print("  Benutzername: admin")
            print("  Passwort: admin123")
            print("  WARNUNG: BITTE SOFORT AENDERN!")
            print("="*60 + "\n")
    except Exception as e:
        print(f"Fehler beim Erstellen der Standard-Organisation: {e}")

    # Erstelle Standard-Wartungstypen für alle Organisationen die noch keine haben
    try:
        orgs = conn.execute('SELECT id FROM organizations').fetchall()
        for org in orgs:
            type_count = conn.execute(
                'SELECT COUNT(*) as count FROM maintenance_types WHERE organization_id = ?',
                (org['id'],)
            ).fetchone()['count']
            if type_count == 0:
                default_types = [
                    ('Inspektion', 'Regelmäßige Sichtprüfung und Kontrolle', '#3b82f6', 'search', 90),
                    ('Reparatur', 'Fehlerbehebung und Instandsetzung', '#ef4444', 'tool', None),
                    ('Kalibrierung', 'Justierung und Eichung von Messgeräten', '#8b5cf6', 'target', 365),
                    ('Reinigung', 'Reinigung und Pflege', '#22c55e', 'sparkles', 30),
                    ('Software-Update', 'Firmware- und Software-Aktualisierung', '#06b6d4', 'cpu', 180),
                    ('Sicherheitsprüfung', 'Prüfung der Sicherheitseinrichtungen', '#f59e0b', 'shield', 365),
                ]
                for name, desc, color, icon, interval in default_types:
                    conn.execute(
                        '''INSERT INTO maintenance_types
                           (organization_id, name, description, color, icon, default_interval_days)
                           VALUES (?, ?, ?, ?, ?, ?)''',
                        (org['id'], name, desc, color, icon, interval)
                    )
                conn.commit()
                print(f"OK: Standard-Wartungstypen für Organisation {org['id']} erstellt")
    except Exception as e:
        print(f"Info: Wartungstypen-Seed - {e}")

    # Migration: Bestehende Wartungsdaten von items nach item_maintenance_schedules überführen
    try:
        schedule_count = conn.execute('SELECT COUNT(*) as count FROM item_maintenance_schedules').fetchone()['count']
        if schedule_count == 0:
            items_with_maintenance = conn.execute('''
                SELECT i.id, i.organization_id, i.maintenance_interval_days,
                       i.last_maintenance_date, i.next_maintenance_date, i.maintenance_notes
                FROM items i
                WHERE i.requires_maintenance = 1
                AND i.maintenance_interval_days IS NOT NULL
            ''').fetchall()

            migrated = 0
            for item in items_with_maintenance:
                mtype = conn.execute(
                    'SELECT id FROM maintenance_types WHERE organization_id = ? AND name = ?',
                    (item['organization_id'], 'Inspektion')
                ).fetchone()
                if mtype:
                    conn.execute('''
                        INSERT OR IGNORE INTO item_maintenance_schedules
                        (item_id, maintenance_type_id, interval_days, last_date, next_date, notes, is_active)
                        VALUES (?, ?, ?, ?, ?, ?, 1)
                    ''', (
                        item['id'], mtype['id'], item['maintenance_interval_days'],
                        item['last_maintenance_date'], item['next_maintenance_date'],
                        item['maintenance_notes']
                    ))
                    migrated += 1

            # Backfill organization_id auf bestehende maintenance_history Einträge
            conn.execute('''
                UPDATE maintenance_history SET organization_id = (
                    SELECT i.organization_id FROM items i WHERE i.id = maintenance_history.item_id
                )
                WHERE organization_id IS NULL
            ''')

            conn.commit()
            if migrated > 0:
                print(f"OK: {migrated} bestehende Wartungsdaten migriert")
    except Exception as e:
        print(f"Info: Wartungsdaten-Migration - {e}")

    conn.close()

def get_db_connection():
    """Erstellt eine Datenbankverbindung"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    """Hasht ein Passwort mit bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed):
    """Verifiziert ein Passwort gegen einen bcrypt-Hash"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

def allowed_file(filename):
    """Prüft ob die Dateiendung erlaubt ist"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def secure_filename_custom(filename):
    """Erstellt einen sicheren Dateinamen"""
    # Behalte die Endung
    if '.' in filename:
        name, ext = filename.rsplit('.', 1)
        ext = ext.lower()
    else:
        name = filename
        ext = ''

    # Erstelle eindeutigen Namen mit Timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    random_suffix = secrets.token_hex(4)

    if ext:
        return f"{timestamp}_{random_suffix}.{ext}"
    return f"{timestamp}_{random_suffix}"

def csrf_protect_api():
    """Decorator für CSRF-Schutz bei API-Routen"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if request.method in ['POST', 'PUT', 'DELETE']:
                csrf.protect()
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def sanitize_string(value, max_length=255):
    """Sanitiert Strings und entfernt gefährliche Zeichen"""
    if not value:
        return value
    # Entferne führende/nachfolgende Leerzeichen
    value = str(value).strip()
    # Begrenze Länge
    if len(value) > max_length:
        value = value[:max_length]
    return value

def validate_number(value, min_val=None, max_val=None):
    """Validiert numerische Werte"""
    try:
        num = float(value) if '.' in str(value) else int(value)
        if min_val is not None and num < min_val:
            return None
        if max_val is not None and num > max_val:
            return None
        return num
    except (ValueError, TypeError):
        return None

def create_slug(text):
    """Erstellt einen URL-freundlichen Slug"""
    import re
    # Konvertiere zu Kleinbuchstaben
    text = text.lower()
    # Ersetze Umlaute
    text = text.replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss')
    # Entferne alle Zeichen außer Buchstaben, Zahlen und Bindestrichen
    text = re.sub(r'[^a-z0-9-]', '-', text)
    # Ersetze mehrere Bindestriche durch einen
    text = re.sub(r'-+', '-', text)
    # Entferne Bindestriche am Anfang und Ende
    text = text.strip('-')
    return text

def verify_user(username, password):
    """Überprüft Benutzername und Passwort"""
    conn = get_db_connection()

    user = conn.execute('''
        SELECT u.*, o.name as organization_name, o.is_active as org_active
        FROM users u
        JOIN organizations o ON u.organization_id = o.id
        WHERE u.username = ?
    ''', (username,)).fetchone()

    if user and verify_password(password, user['password_hash']):
        # Prüfe ob Organisation aktiv ist
        if not user['org_active']:
            conn.close()
            return None
        # Aktualisiere letzten Login
        conn.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?',
                    (user['id'],))
        conn.commit()
        conn.close()
        return dict(user)

    conn.close()
    return None

def create_user(username, password, email=None, is_admin=False, organization_id=None):
    """Erstellt einen neuen Benutzer"""
    # Input-Validierung
    if not username or len(username) < 3:
        return False, "Benutzername muss mindestens 3 Zeichen lang sein"
    if not organization_id:
        return False, "Keine Organisation angegeben"

    # Passwort-Validierung
    is_valid, message = validate_password(password)
    if not is_valid:
        return False, message

    conn = get_db_connection()
    password_hash = hash_password(password)

    try:
        conn.execute('''INSERT INTO users (organization_id, username, password_hash, email, is_admin, is_org_owner)
                       VALUES (?, ?, ?, ?, ?, 0)''',
                    (organization_id, username, password_hash, email, is_admin))
        conn.commit()
        conn.close()
        return True, "Benutzer erfolgreich erstellt"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Benutzername existiert bereits"

def change_password(username, old_password, new_password):
    """Ändert das Passwort eines Benutzers"""
    # Passwort-Validierung
    is_valid, message = validate_password(new_password)
    if not is_valid:
        return False, message

    # Erst verifizieren
    user = verify_user(username, old_password)
    if not user:
        return False, "Altes Passwort ist falsch"

    conn = get_db_connection()
    new_password_hash = hash_password(new_password)

    conn.execute('UPDATE users SET password_hash = ? WHERE username = ?',
                (new_password_hash, username))
    conn.commit()
    conn.close()
    return True, "Passwort erfolgreich geändert"

def export_users_to_drive():
    """Exportiert Benutzer zu Google Drive"""
    try:
        conn = get_db_connection()
        users = conn.execute('SELECT username, password_hash, email, is_admin FROM users').fetchall()
        conn.close()
        
        # Erstelle JSON
        users_data = {
            'users': [dict(user) for user in users],
            'exported_at': datetime.now().isoformat()
        }
        
        # Speichere lokal
        users_file = 'users_backup.json'
        with open(users_file, 'w') as f:
            json.dump(users_data, f, indent=2)
        
        # Upload zu Google Drive
        from gdrive_sync import GoogleDriveSync
        sync = GoogleDriveSync()
        
        if sync.authenticate():
            sync.get_or_create_folder()
            
            # Upload users file
            from googleapiclient.http import MediaFileUpload
            file_metadata = {
                'name': f'users_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json',
                'parents': [sync.folder_id]
            }
            media = MediaFileUpload(users_file, mimetype='application/json')
            file = sync.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink'
            ).execute()
            
            # Lokale Datei löschen
            os.remove(users_file)
            
            return {
                'success': True,
                'message': 'Benutzer erfolgreich zu Google Drive exportiert',
                'file_id': file.get('id')
            }
    except Exception as e:
        return {
            'success': False,
            'message': f'Fehler beim Export: {str(e)}'
        }

def get_base_url():
    """Ermittelt die Basis-URL der Anwendung (dynamisch)"""
    # Versuche aus Request zu lesen
    if request:
        return request.host_url.rstrip('/')
    # Fallback für localhost
    return 'http://localhost:5000'

def generate_qr_code(item_id, item_data):
    """Generiert einen QR-Code für ein Item"""
    # QR-Code Daten: Dynamische URL zum Item
    base_url = get_base_url()
    qr_data = f"{base_url}/item/{item_id}"
    
    # QR-Code erstellen
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    # Bild erstellen
    img = qr.make_image(fill_color="black", back_color="white")
    
    # In BytesIO speichern
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    return buffer

def generate_qr_code_base64(item_id, item_data):
    """Generiert einen QR-Code als Base64 String"""
    buffer = generate_qr_code(item_id, item_data)
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

def generate_barcode(item_id, item_data):
    """Generiert einen Barcode für ein Item (Code128)"""
    # Erstelle Barcode-Daten: Item-ID mit Präfix
    barcode_data = f"ITEM{str(item_id).zfill(8)}"  # z.B. ITEM00000001

    # Code128 Barcode erstellen
    code128 = barcode.get_barcode_class('code128')
    barcode_instance = code128(barcode_data, writer=ImageWriter())

    # In BytesIO speichern
    buffer = BytesIO()
    barcode_instance.write(buffer, options={
        'module_width': 0.3,
        'module_height': 10.0,
        'quiet_zone': 2.0,
        'font_size': 10,
        'text_distance': 3.0,
        'write_text': True
    })
    buffer.seek(0)

    return buffer

def generate_barcode_base64(item_id, item_data):
    """Generiert einen Barcode als Base64 String"""
    buffer = generate_barcode(item_id, item_data)
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

def init_google_drive():
    """Initialisiert Google Drive Sync und erstellt credentials.json wenn nötig"""
    credentials_file = 'credentials.json'
    
    # Prüfe ob credentials.json existiert
    if not os.path.exists(credentials_file):
        print("\n" + "="*60)
        print("⚠️  Google Drive Credentials nicht gefunden!")
        print("="*60)
        print("\nErstelle Template für credentials.json...")
        
        # Erstelle Template credentials.json
        template = {
            "installed": {
                "client_id": "IHRE_CLIENT_ID.apps.googleusercontent.com",
                "project_id": "ihr-projekt-name",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": "IHR_CLIENT_SECRET",
                "redirect_uris": ["http://localhost"]
            }
        }
        
        with open(credentials_file, 'w') as f:
            json.dump(template, f, indent=4)
        
        print(f"✓ Template erstellt: {credentials_file}")
        print("\nSo richten Sie Google Drive ein:")
        print("1. Gehen Sie zu: https://console.cloud.google.com/")
        print("2. Erstellen Sie ein neues Projekt")
        print("3. Aktivieren Sie die 'Google Drive API'")
        print("4. Erstellen Sie OAuth 2.0 Desktop Credentials")
        print("5. Laden Sie die JSON-Datei herunter")
        print("6. Ersetzen Sie die credentials.json mit Ihrer Datei")
        print("7. Starten Sie die Anwendung neu")
        print("\nDetails: Siehe README.md → Google Drive Setup")
        print("="*60 + "\n")
        
        sync_status['status'] = 'Credentials fehlen - Template erstellt'
        return False
    
    # Prüfe ob es das Template ist
    try:
        with open(credentials_file, 'r') as f:
            creds = json.load(f)
            if 'installed' in creds:
                client_id = creds['installed'].get('client_id', '')
                if 'IHRE_CLIENT_ID' in client_id:
                    print("\n⚠️  Bitte ersetzen Sie credentials.json mit Ihren echten Google Credentials!")
                    print("Siehe README.md für Anleitung.\n")
                    sync_status['status'] = 'Template vorhanden - Echte Credentials benötigt'
                    return False
    except:
        pass
    
    sync_status['status'] = 'Bereit für Sync'
    return True

def sync_to_google_drive():
    """Synchronisiert die Datenbank zu Google Drive"""
    try:
        from gdrive_sync import GoogleDriveSync
        
        sync = GoogleDriveSync()
        
        # Authentifizierung
        if not sync.authenticate():
            return {
                'success': False,
                'message': 'Authentifizierung fehlgeschlagen'
            }
        
        # Ordner erstellen/finden
        sync.get_or_create_folder()
        
        # Datenbank hochladen
        result = sync.upload_database()
        
        # Status aktualisieren
        sync_status['last_sync'] = datetime.now().isoformat()
        sync_status['status'] = 'Erfolgreich'
        
        return {
            'success': True,
            'message': 'Erfolgreich zu Google Drive synchronisiert',
            'file_id': result.get('id'),
            'link': result.get('webViewLink')
        }
        
    except ImportError:
        return {
            'success': False,
            'message': 'Google Drive Modul nicht verfügbar'
        }
    except FileNotFoundError as e:
        return {
            'success': False,
            'message': str(e)
        }
    except Exception as e:
        return {
            'success': False,
            'message': f'Fehler beim Sync: {str(e)}'
        }

# ============= PUBLIC ROUTES =============

@app.route('/landing')
def landing():
    """Landing Page"""
    return render_template('landing.html')

@app.route('/register', methods=['GET'])
def register_page():
    """Registrierungs-Seite"""
    if 'logged_in' in session:
        return redirect(url_for('index'))
    return render_template('register.html')

# ============= LOGIN ROUTES =============

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit(os.getenv('LOGIN_RATE_LIMIT', '5 per minute'))
def login():
    """Login-Seite"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember')

        # Prüfe Account-Locking
        ip_address = get_remote_address()
        is_locked, locked_until = is_account_locked(ip_address)

        if is_locked:
            remaining_time = (locked_until - datetime.now()).total_seconds() // 60
            return render_template('login.html',
                error=f'Konto gesperrt. Zu viele fehlgeschlagene Login-Versuche. Bitte warten Sie noch {int(remaining_time)} Minuten.')

        user = verify_user(username, password)

        if user:
            # Login erfolgreich - Reset failed attempts
            reset_failed_logins(ip_address)

            session['logged_in'] = True
            session['user_id'] = user['id']
            session['username'] = username
            session['organization_id'] = user['organization_id']
            session['organization_name'] = user['organization_name']
            session['is_admin'] = user['is_admin']
            session['is_org_owner'] = user['is_org_owner']

            if remember:
                session.permanent = True
            else:
                session.permanent = False  # Session läuft nach 30 Min ab

            # Update last login
            conn = get_db_connection()
            conn.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user['id'],))
            conn.commit()
            conn.close()

            return redirect(url_for('index'))
        else:
            # Login fehlgeschlagen - Record attempt
            just_locked = record_failed_login(ip_address)

            if just_locked:
                return render_template('login.html',
                    error=f'Konto gesperrt! Zu viele fehlgeschlagene Login-Versuche. Versuchen Sie es in {LOCKOUT_DURATION.total_seconds() // 60:.0f} Minuten erneut.')
            else:
                attempts_left = MAX_LOGIN_ATTEMPTS - failed_login_attempts[ip_address]['count']
                return render_template('login.html',
                    error=f'Falscher Benutzername oder Passwort. Noch {attempts_left} Versuche übrig.')

    # Wenn bereits eingeloggt, zur Hauptseite
    if 'logged_in' in session:
        return redirect(url_for('index'))

    # Check for success message from registration
    success = None
    if request.args.get('registered') == 'true':
        success = 'Organisation erfolgreich erstellt! Bitte melden Sie sich an.'

    return render_template('login.html', success=success)

@app.route('/logout')
def logout():
    """Logout"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/profile')
@login_required
def profile():
    """Profil-Seite"""
    conn = get_db_connection()
    user = conn.execute(
        'SELECT email, notify_low_stock, notify_maintenance, notify_backup FROM users WHERE id = ?',
        (session.get('user_id'),)
    ).fetchone()
    conn.close()

    return render_template('profile.html',
                          username=session.get('username'),
                          is_admin=session.get('is_admin'),
                          email=user['email'] if user else '',
                          notify_low_stock=user['notify_low_stock'] if user else 1,
                          notify_maintenance=user['notify_maintenance'] if user else 1,
                          notify_backup=user['notify_backup'] if user else 0)

@app.route('/settings')
@login_required
def settings():
    """Einstellungsseite"""
    return render_template('settings.html',
                          username=session.get('username'),
                          is_admin=session.get('is_admin'))

@app.route('/users')
@admin_required
def users_page():
    """Benutzerverwaltung (nur Admin)"""
    return render_template('users.html')

# ============= RECHTLICHE SEITEN =============

@app.route('/impressum')
def impressum():
    """Impressum-Seite"""
    return render_template('impressum.html')

@app.route('/datenschutz')
def datenschutz():
    """Datenschutzerklärung-Seite"""
    return render_template('datenschutz.html')

@app.route('/agb')
def agb():
    """AGB / Nutzungsbedingungen-Seite"""
    return render_template('agb.html')

# ============= ROUTES =============

@app.route('/offline')
def offline():
    """Offline-Fallback-Seite für PWA"""
    return render_template('offline.html')

@app.route('/')
def index():
    """Hauptseite - Landing Page oder Dashboard"""
    if 'logged_in' in session:
        return render_template('index.html',
                             username=session.get('username'),
                             organization_name=session.get('organization_name'))
    else:
        return render_template('landing.html')

@app.route('/item/<int:id>')
@login_required
def item_detail(id):
    """Detailseite für einen Artikel (für QR-Code-Scan)"""
    conn = get_db_connection()
    item = conn.execute('''SELECT i.*, c.name as category_name, l.name as location_name
                          FROM items i
                          LEFT JOIN categories c ON i.category_id = c.id
                          LEFT JOIN locations l ON i.location_id = l.id
                          WHERE i.id = ?''', (id,)).fetchone()
    
    if not item:
        conn.close()
        return "<h1>Artikel nicht gefunden</h1><p><a href='/'>Zurück zur Übersicht</a></p>", 404
    
    # Letzte Bewegungen holen
    movements = conn.execute('''SELECT * FROM movements 
                               WHERE item_id = ? 
                               ORDER BY created_at DESC 
                               LIMIT 10''', (id,)).fetchall()
    conn.close()
    
    return render_template('item_detail.html', item=dict(item), movements=[dict(m) for m in movements])

@app.route('/api/register', methods=['POST'])
@limiter.limit("10 per hour")
def register_organization():
    """Registriert eine neue Organisation ODER einen Benutzer zu bestehender Organisation"""
    try:
        data = request.json
        reg_type = data.get('type', 'organization')

        # FALL 1: Neue Organisation erstellen
        if reg_type == 'organization':
            # Validierung
            required_fields = ['org_name', 'username', 'password']
            for field in required_fields:
                if not data.get(field):
                    return jsonify({'success': False, 'message': f'Feld "{field}" ist erforderlich'}), 400

            # Organisationsname validieren
            org_name = sanitize_string(data['org_name'], 100)
            org_slug = create_slug(org_name)

            # Prüfe ob Organisation bereits existiert
            conn = get_db_connection()
            existing_org = conn.execute('SELECT id FROM organizations WHERE slug = ?', (org_slug,)).fetchone()
            if existing_org:
                conn.close()
                return jsonify({'success': False, 'message': 'Eine Organisation mit diesem Namen existiert bereits'}), 400

            # Prüfe ob Benutzername bereits vergeben ist
            existing_user = conn.execute('SELECT id FROM users WHERE username = ?', (data['username'],)).fetchone()
            if existing_user:
                conn.close()
                return jsonify({'success': False, 'message': 'Benutzername bereits vergeben'}), 400

            # Plan-Limits setzen (free als Standard)
            plan = 'free'
            max_users = 5
            max_items = 1000

            # Organisation erstellen
            org_cursor = conn.execute('''
                INSERT INTO organizations (name, slug, email, phone, plan, max_users, max_items)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (org_name, org_slug, '', '', plan, max_users, max_items))

            organization_id = org_cursor.lastrowid

            # Admin-Benutzer erstellen
            password_hash = hash_password(data['password'])

            conn.execute('''
                INSERT INTO users (organization_id, username, password_hash, email, first_name, last_name, is_admin, is_org_owner)
                VALUES (?, ?, ?, ?, ?, ?, 1, 1)
            ''', (organization_id, data['username'], password_hash, '', '', ''))

            conn.commit()
            conn.close()

            return jsonify({
                'success': True,
                'message': 'Organisation erfolgreich erstellt',
                'organization_id': organization_id,
                'organization_slug': org_slug
            })

        # FALL 2: Benutzer zu bestehender Organisation hinzufügen (mit Einladungstoken)
        elif reg_type == 'user':
            # Validierung
            required_fields = ['invitation_token', 'username', 'password']
            for field in required_fields:
                if not data.get(field):
                    return jsonify({'success': False, 'message': f'Feld "{field}" ist erforderlich'}), 400

            conn = get_db_connection()

            # Validiere Einladungstoken
            token = conn.execute('''SELECT t.*, o.name as org_name, o.max_users
                                   FROM invitation_tokens t
                                   JOIN organizations o ON t.organization_id = o.id
                                   WHERE t.token = ?''', (data['invitation_token'],)).fetchone()

            if not token:
                conn.close()
                return jsonify({'success': False, 'message': 'Ungültiger Einladungscode'}), 400

            # Prüfe ob bereits verwendet
            if token['is_used']:
                conn.close()
                return jsonify({'success': False, 'message': 'Dieser Einladungscode wurde bereits verwendet'}), 400

            # Prüfe ob abgelaufen
            if token['expires_at']:
                expires_at = datetime.fromisoformat(token['expires_at'])
                if datetime.now() > expires_at:
                    conn.close()
                    return jsonify({'success': False, 'message': 'Dieser Einladungscode ist abgelaufen'}), 400

            organization_id = token['organization_id']

            # Prüfe Benutzerlimit
            user_count = conn.execute('SELECT COUNT(*) as count FROM users WHERE organization_id = ?',
                                     (organization_id,)).fetchone()['count']
            if user_count >= token['max_users']:
                conn.close()
                return jsonify({'success': False, 'message': 'Maximale Benutzeranzahl erreicht'}), 400

            # Prüfe ob Benutzername bereits in dieser Organisation vergeben ist
            existing_user = conn.execute('SELECT id FROM users WHERE organization_id = ? AND username = ?',
                                        (organization_id, data['username'])).fetchone()
            if existing_user:
                conn.close()
                return jsonify({'success': False, 'message': 'Benutzername bereits vergeben'}), 400

            # Benutzer erstellen
            password_hash = hash_password(data['password'])

            cursor = conn.execute('''
                INSERT INTO users (organization_id, username, password_hash, email, first_name, last_name, is_admin, is_org_owner)
                VALUES (?, ?, ?, ?, ?, ?, 0, 0)
            ''', (organization_id, data['username'], password_hash, '', '', ''))

            user_id = cursor.lastrowid

            # Token als verwendet markieren
            conn.execute('''UPDATE invitation_tokens
                           SET is_used = 1, used_by = ?, used_at = CURRENT_TIMESTAMP
                           WHERE id = ?''', (user_id, token['id']))

            conn.commit()
            conn.close()

            return jsonify({
                'success': True,
                'message': 'Benutzer erfolgreich registriert'
            })

        else:
            return jsonify({'success': False, 'message': 'Ungültiger Registrierungstyp'}), 400

    except Exception as e:
        return jsonify({'success': False, 'message': f'Fehler bei der Registrierung: {str(e)}'}), 500

@app.route('/api/csrf-token')
@login_required
def get_csrf_token():
    """Get fresh CSRF token"""
    from flask_wtf.csrf import generate_csrf
    return jsonify({'csrf_token': generate_csrf()})

@app.route('/api/dashboard')
@login_required
def dashboard():
    """Dashboard Statistiken"""
    conn = get_db_connection()
    organization_id = session.get('organization_id')

    total_items = conn.execute('SELECT COUNT(*) as count FROM items WHERE organization_id = ?',
                               (organization_id,)).fetchone()['count']
    total_categories = conn.execute('SELECT COUNT(*) as count FROM categories WHERE organization_id = ?',
                                    (organization_id,)).fetchone()['count']
    total_locations = conn.execute('SELECT COUNT(*) as count FROM locations WHERE organization_id = ?',
                                   (organization_id,)).fetchone()['count']
    low_stock = conn.execute('SELECT COUNT(*) as count FROM items WHERE organization_id = ? AND quantity <= min_quantity',
                            (organization_id,)).fetchone()['count']

    total_value = conn.execute('SELECT SUM(quantity * price) as value FROM items WHERE organization_id = ?',
                              (organization_id,)).fetchone()['value'] or 0

    conn.close()

    return jsonify({
        'total_items': total_items,
        'total_categories': total_categories,
        'total_locations': total_locations,
        'low_stock_items': low_stock,
        'total_value': round(total_value, 2),
        'sync_status': sync_status,
        'organization_id': organization_id
    })

@app.route('/api/organization-info')
@login_required
def organization_info():
    """Organisationsinformationen abrufen"""
    conn = get_db_connection()
    organization_id = session.get('organization_id')

    org = conn.execute('''SELECT id, name, max_users, created_at
                          FROM organizations
                          WHERE id = ?''', (organization_id,)).fetchone()

    user_count = conn.execute('''SELECT COUNT(*) as count
                                 FROM users
                                 WHERE organization_id = ?''', (organization_id,)).fetchone()['count']

    conn.close()

    return jsonify({
        'id': org['id'],
        'name': org['name'],
        'max_users': org['max_users'],
        'current_users': user_count,
        'created_at': org['created_at']
    })

# ============= INVITATION TOKENS =============

@app.route('/api/invitations', methods=['GET', 'POST'])
@admin_required
@csrf_protect_api()
def invitations():
    """Einladungstokens verwalten (nur Admin)"""
    conn = get_db_connection()
    organization_id = session.get('organization_id')
    user_id = session.get('user_id')

    if request.method == 'POST':
        # Neuen Einladungstoken erstellen
        data = request.json
        expires_hours = data.get('expires_hours', 24)  # Standard: 24h

        # Token generieren (sicherer 16-stelliger Code)
        token = secrets.token_urlsafe(12)

        # Ablaufdatum berechnen
        expires_at = datetime.now() + timedelta(hours=expires_hours) if expires_hours > 0 else None

        conn.execute('''INSERT INTO invitation_tokens
                        (organization_id, token, created_by, expires_at)
                        VALUES (?, ?, ?, ?)''',
                     (organization_id, token, user_id, expires_at))
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'token': token,
            'expires_at': expires_at.isoformat() if expires_at else None
        })

    # GET - Alle Tokens anzeigen
    tokens = conn.execute('''SELECT t.*, u.username as created_by_username
                            FROM invitation_tokens t
                            JOIN users u ON t.created_by = u.id
                            WHERE t.organization_id = ?
                            ORDER BY t.created_at DESC''',
                         (organization_id,)).fetchall()
    conn.close()
    return jsonify([dict(t) for t in tokens])

@app.route('/api/invitations/<int:token_id>', methods=['DELETE'])
@admin_required
@csrf_protect_api()
def delete_invitation(token_id):
    """Einladungstoken löschen"""
    conn = get_db_connection()
    organization_id = session.get('organization_id')

    conn.execute('''DELETE FROM invitation_tokens
                    WHERE id = ? AND organization_id = ?''',
                (token_id, organization_id))
    conn.commit()
    conn.close()

    return jsonify({'success': True})

@app.route('/api/invitations/validate', methods=['POST'])
@limiter.limit("10 per hour")
def validate_invitation():
    """Einladungstoken validieren (öffentlich)"""
    data = request.json
    token = data.get('token')

    if not token:
        return jsonify({'valid': False, 'message': 'Kein Token angegeben'}), 400

    conn = get_db_connection()

    # Token suchen
    inv = conn.execute('''SELECT t.*, o.name as org_name, o.max_users
                         FROM invitation_tokens t
                         JOIN organizations o ON t.organization_id = o.id
                         WHERE t.token = ?''', (token,)).fetchone()

    if not inv:
        conn.close()
        return jsonify({'valid': False, 'message': 'Ungültiger Einladungscode'})

    # Prüfen ob bereits verwendet
    if inv['is_used']:
        conn.close()
        return jsonify({'valid': False, 'message': 'Dieser Einladungscode wurde bereits verwendet'})

    # Prüfen ob abgelaufen
    if inv['expires_at']:
        expires_at = datetime.fromisoformat(inv['expires_at'])
        if datetime.now() > expires_at:
            conn.close()
            return jsonify({'valid': False, 'message': 'Dieser Einladungscode ist abgelaufen'})

    # Prüfen ob Organisation voll ist
    user_count = conn.execute('''SELECT COUNT(*) as count
                                FROM users
                                WHERE organization_id = ?''',
                            (inv['organization_id'],)).fetchone()['count']

    if user_count >= inv['max_users']:
        conn.close()
        return jsonify({'valid': False, 'message': 'Die Organisation hat bereits die maximale Anzahl an Benutzern erreicht'})

    conn.close()

    return jsonify({
        'valid': True,
        'organization_name': inv['org_name'],
        'organization_id': inv['organization_id']
    })

# ============= USER MANAGEMENT =============

@app.route('/api/users', methods=['GET', 'POST'])
@admin_required
@csrf_protect_api()
def users():
    """Benutzerverwaltung (nur Admin)"""
    conn = get_db_connection()

    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        password = data.get('password')
        email = data.get('email')
        is_admin = data.get('is_admin', False)
        organization_id = session.get('organization_id')

        success, message = create_user(username, password, email, is_admin, organization_id)
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'message': message}), 400

    # GET - Alle Benutzer der Organisation (ohne Passwort-Hash)
    organization_id = session.get('organization_id')
    users = conn.execute('''SELECT id, username, email, is_admin, created_at, last_login
                           FROM users
                           WHERE organization_id = ?
                           ORDER BY username''', (organization_id,)).fetchall()
    conn.close()
    return jsonify([dict(user) for user in users])

@app.route('/api/users/<int:id>', methods=['GET', 'PUT', 'DELETE'])
@admin_required
def user_detail(id):
    """Einzelner Benutzer - abrufen, aktualisieren oder löschen (nur Admin)"""
    # CSRF-Schutz nur für modifizierende Anfragen
    if request.method in ['PUT', 'DELETE']:
        csrf.protect()

    conn = get_db_connection()
    organization_id = session.get('organization_id')

    if request.method == 'GET':
        # Einzelnen Benutzer abrufen
        user = conn.execute('''SELECT id, username, email, is_admin, created_at, last_login
                              FROM users
                              WHERE id = ? AND organization_id = ?''',
                          (id, organization_id)).fetchone()
        conn.close()

        if not user:
            return jsonify({'success': False, 'message': 'Benutzer nicht gefunden'}), 404

        return jsonify(dict(user))

    elif request.method == 'PUT':
        # Benutzer aktualisieren
        data = request.json
        username = data.get('username')
        email = data.get('email')
        is_admin = data.get('is_admin', False)
        password = data.get('password')  # Optional

        # Prüfe ob Benutzer zur Organisation gehört
        user = conn.execute('SELECT username FROM users WHERE id = ? AND organization_id = ?',
                          (id, organization_id)).fetchone()

        if not user:
            conn.close()
            return jsonify({'success': False, 'message': 'Benutzer nicht gefunden'}), 404

        try:
            # Update Benutzerdaten
            if password:
                # Mit neuem Passwort
                password_hash = generate_password_hash(password)
                conn.execute('''UPDATE users
                              SET username = ?, email = ?, is_admin = ?, password_hash = ?
                              WHERE id = ? AND organization_id = ?''',
                          (username, email, is_admin, password_hash, id, organization_id))
            else:
                # Ohne Passwort-Änderung
                conn.execute('''UPDATE users
                              SET username = ?, email = ?, is_admin = ?
                              WHERE id = ? AND organization_id = ?''',
                          (username, email, is_admin, id, organization_id))

            conn.commit()
            conn.close()
            return jsonify({'success': True, 'message': 'Benutzer aktualisiert'})

        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({'success': False, 'message': 'Benutzername bereits vergeben'}), 400

    elif request.method == 'DELETE':
        # Benutzer löschen
        # Verhindere Löschen des eigenen Accounts
        user = conn.execute('SELECT username FROM users WHERE id = ? AND organization_id = ?',
                          (id, organization_id)).fetchone()

        if not user:
            conn.close()
            return jsonify({'success': False, 'message': 'Benutzer nicht gefunden'}), 404

        if user['username'] == session.get('username'):
            conn.close()
            return jsonify({'success': False, 'message': 'Sie können Ihren eigenen Account nicht löschen'}), 400

        conn.execute('DELETE FROM users WHERE id = ? AND organization_id = ?', (id, organization_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Benutzer gelöscht'})

@app.route('/api/profile/change-password', methods=['POST'])
@login_required
@csrf_protect_api()
def change_user_password():
    """Passwort ändern"""
    data = request.json
    old_password = data.get('old_password')
    new_password = data.get('new_password')

    username = session.get('username')
    success, message = change_password(username, old_password, new_password)

    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'message': message}), 400

@app.route('/api/profile/update-notifications', methods=['POST'])
@login_required
@csrf_protect_api()
def update_notification_settings():
    """E-Mail und Benachrichtigungs-Einstellungen aktualisieren"""
    data = request.json
    user_id = session.get('user_id')

    email = data.get('email', '').strip()
    notify_low_stock = 1 if data.get('notify_low_stock', True) else 0
    notify_maintenance = 1 if data.get('notify_maintenance', True) else 0
    notify_backup = 1 if data.get('notify_backup', False) else 0

    try:
        conn = get_db_connection()
        conn.execute('''UPDATE users
                       SET email = ?, notify_low_stock = ?, notify_maintenance = ?, notify_backup = ?
                       WHERE id = ?''',
                    (email if email else None, notify_low_stock, notify_maintenance, notify_backup, user_id))
        conn.commit()
        conn.close()

        return jsonify({'success': True, 'message': 'Benachrichtigungs-Einstellungen gespeichert'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/users/export', methods=['POST'])
@admin_required
@csrf_protect_api()
def export_users():
    """Exportiert Benutzer zu Google Drive (nur Admin)"""
    result = export_users_to_drive()
    return jsonify(result)

# ============= KATEGORIEN =============

@app.route('/api/categories', methods=['GET', 'POST'])
@login_required
@csrf_protect_api()
def categories():
    conn = get_db_connection()
    organization_id = session.get('organization_id')

    if request.method == 'POST':
        data = request.json
        try:
            conn.execute('INSERT INTO categories (organization_id, name, description) VALUES (?, ?, ?)',
                        (organization_id, data['name'], data.get('description', '')))
            conn.commit()
            return jsonify({'success': True, 'message': 'Kategorie erstellt'})
        except sqlite3.IntegrityError:
            return jsonify({'success': False, 'message': 'Kategorie existiert bereits'}), 400
        finally:
            conn.close()

    categories = conn.execute('SELECT * FROM categories WHERE organization_id = ? ORDER BY name',
                             (organization_id,)).fetchall()
    conn.close()
    return jsonify([dict(cat) for cat in categories])

@app.route('/api/categories/<int:id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
@csrf_protect_api()
def category(id):
    conn = get_db_connection()
    
    if request.method == 'DELETE':
        conn.execute('DELETE FROM categories WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Kategorie gelöscht'})
    
    if request.method == 'PUT':
        data = request.json
        conn.execute('UPDATE categories SET name = ?, description = ? WHERE id = ?',
                    (data['name'], data.get('description', ''), id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Kategorie aktualisiert'})
    
    category = conn.execute('SELECT * FROM categories WHERE id = ?', (id,)).fetchone()
    conn.close()
    return jsonify(dict(category) if category else {})

# ============= STANDORTE =============

@app.route('/api/locations', methods=['GET', 'POST'])
@login_required
@csrf_protect_api()
def locations():
    conn = get_db_connection()
    organization_id = session.get('organization_id')

    if request.method == 'POST':
        data = request.json
        try:
            conn.execute('INSERT INTO locations (organization_id, name, description) VALUES (?, ?, ?)',
                        (organization_id, data['name'], data.get('description', '')))
            conn.commit()
            return jsonify({'success': True, 'message': 'Standort erstellt'})
        except sqlite3.IntegrityError:
            return jsonify({'success': False, 'message': 'Standort existiert bereits'}), 400
        finally:
            conn.close()

    locations = conn.execute('SELECT * FROM locations WHERE organization_id = ? ORDER BY name',
                            (organization_id,)).fetchall()
    conn.close()
    return jsonify([dict(loc) for loc in locations])

@app.route('/api/locations/<int:id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
@csrf_protect_api()
def location(id):
    conn = get_db_connection()
    
    if request.method == 'DELETE':
        conn.execute('DELETE FROM locations WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Standort gelöscht'})
    
    if request.method == 'PUT':
        data = request.json
        conn.execute('UPDATE locations SET name = ?, description = ? WHERE id = ?',
                    (data['name'], data.get('description', ''), id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Standort aktualisiert'})
    
    location = conn.execute('SELECT * FROM locations WHERE id = ?', (id,)).fetchone()
    conn.close()
    return jsonify(dict(location) if location else {})

# ============= ARTIKEL =============

@app.route('/api/items', methods=['GET', 'POST'])
@login_required
@csrf_protect_api()
def items():
    conn = get_db_connection()
    organization_id = session.get('organization_id')

    # Validiere dass organization_id vorhanden ist
    if not organization_id:
        conn.close()
        return jsonify({'success': False, 'message': 'Keine Organisation in Session gefunden. Bitte neu einloggen.'}), 401

    if request.method == 'POST':
        data = request.json

        # Validierung
        name = sanitize_string(data.get('name'), 255)
        if not name:
            return jsonify({'success': False, 'message': 'Name ist erforderlich'}), 400

        quantity = validate_number(data.get('quantity', 0), min_val=0, max_val=999999999)
        min_quantity = validate_number(data.get('min_quantity', 0), min_val=0, max_val=999999999)
        price = validate_number(data.get('price', 0.0), min_val=0)

        if quantity is None or min_quantity is None or price is None:
            return jsonify({'success': False, 'message': f'Ungültige numerische Werte'}), 400

        # Wartungsfelder konvertieren
        requires_maintenance = data.get('requires_maintenance', False)
        maintenance_interval_days = None
        if data.get('maintenance_interval_days'):
            try:
                maintenance_interval_days = int(data.get('maintenance_interval_days'))
            except (ValueError, TypeError):
                maintenance_interval_days = None

        last_maintenance_date = data.get('last_maintenance_date') or None
        next_maintenance_date = data.get('next_maintenance_date') or None
        maintenance_notes = data.get('maintenance_notes') or None

        # SKU konvertieren - leerer String wird zu NULL
        sku = sanitize_string(data.get('sku'), 100)
        if sku == '' or sku is None:
            sku = None  # NULL statt leerem String

        # Barcode konvertieren - leerer String wird zu NULL
        barcode = sanitize_string(data.get('barcode'), 100)
        if barcode == '' or barcode is None:
            barcode = None

        # Gruppen-Felder
        is_group = bool(data.get('is_group', False))
        group_id = data.get('group_id') or None
        if group_id:
            group_id = int(group_id)

        # Gruppen-Validierung
        if is_group and group_id:
            conn.close()
            return jsonify({'success': False, 'message': 'Gruppen können nicht in andere Gruppen verschachtelt werden'}), 400

        if group_id:
            group_item = conn.execute(
                'SELECT id, is_group, organization_id FROM items WHERE id = ?', (group_id,)
            ).fetchone()
            if not group_item or not group_item['is_group'] or group_item['organization_id'] != organization_id:
                conn.close()
                return jsonify({'success': False, 'message': 'Ungültige Gruppe'}), 400

        try:
            cursor = conn.execute('''INSERT INTO items
                (organization_id, sku, name, barcode, description, category_id, location_id, quantity,
                 min_quantity, unit, price, supplier, notes,
                 requires_maintenance, maintenance_interval_days, last_maintenance_date,
                 next_maintenance_date, maintenance_notes, is_group, group_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (organization_id, sku, name, barcode,
                 sanitize_string(data.get('description'), 1000),
                 data.get('category_id') or None, data.get('location_id') or None,
                 quantity, min_quantity,
                 sanitize_string(data.get('unit', 'Stück'), 50), price,
                 sanitize_string(data.get('supplier'), 255),
                 sanitize_string(data.get('notes'), 1000),
                 requires_maintenance,
                 maintenance_interval_days,
                 last_maintenance_date,
                 next_maintenance_date,
                 maintenance_notes,
                 is_group, group_id))
            conn.commit()
            return jsonify({'success': True, 'message': 'Artikel erstellt', 'id': cursor.lastrowid})
        except sqlite3.IntegrityError as e:
            return jsonify({'success': False, 'message': 'SKU existiert bereits'}), 400
        except Exception as e:
            print(f"ERROR beim Erstellen von Artikel: {str(e)}")
            return jsonify({'success': False, 'message': f'Fehler beim Erstellen: {str(e)}'}), 400
        finally:
            conn.close()

    # GET mit optionalen Filtern
    search = request.args.get('search', '')
    category = request.args.get('category')
    location = request.args.get('location')
    low_stock = request.args.get('low_stock')
    group_filter = request.args.get('group')

    query = '''SELECT i.*, c.name as category_name, l.name as location_name,
                      g.name as group_name
               FROM items i
               LEFT JOIN categories c ON i.category_id = c.id
               LEFT JOIN locations l ON i.location_id = l.id
               LEFT JOIN items g ON i.group_id = g.id
               WHERE i.organization_id = ?'''
    params = [organization_id]

    if search:
        query += ' AND (i.name LIKE ? OR i.sku LIKE ? OR i.description LIKE ?)'
        search_param = f'%{search}%'
        params.extend([search_param, search_param, search_param])

    if category:
        query += ' AND i.category_id = ?'
        params.append(category)

    if location:
        query += ' AND i.location_id = ?'
        params.append(location)

    if low_stock:
        query += ' AND i.quantity <= i.min_quantity'

    if group_filter:
        query += ' AND i.group_id = ?'
        params.append(group_filter)

    query += ' ORDER BY i.is_group DESC, i.name'

    items = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(item) for item in items])

@app.route('/api/items/<int:id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
@csrf_protect_api()
def item(id):
    try:
        conn = get_db_connection()
        organization_id = session.get('organization_id')

        if request.method == 'DELETE':
            # Prüfen ob Gruppe noch Kinder hat
            children_count = conn.execute(
                'SELECT COUNT(*) as count FROM items WHERE group_id = ? AND organization_id = ?',
                (id, organization_id)
            ).fetchone()['count']
            if children_count > 0:
                conn.close()
                return jsonify({'success': False, 'message': f'Gruppe enthält noch {children_count} Artikel. Bitte erst Artikel entfernen.'}), 400

            conn.execute('DELETE FROM items WHERE id = ? AND organization_id = ?', (id, organization_id))
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'message': 'Artikel gelöscht'})

        if request.method == 'PUT':
            data = request.json

            # Sicherstellen dass Barcode NULL ist wenn leer
            barcode = data.get('barcode')
            if barcode == '' or barcode is None:
                barcode = None

            # Gruppen-Felder
            is_group = bool(data.get('is_group', False))
            group_id = data.get('group_id') or None
            if group_id:
                group_id = int(group_id)

            # Gruppen können nicht verschachtelt werden
            if is_group and group_id:
                conn.close()
                return jsonify({'success': False, 'message': 'Gruppen können nicht in andere Gruppen verschachtelt werden'}), 400

            # group_id validieren
            if group_id:
                group_item = conn.execute(
                    'SELECT id, is_group, organization_id FROM items WHERE id = ?', (group_id,)
                ).fetchone()
                if not group_item or not group_item['is_group'] or group_item['organization_id'] != organization_id:
                    conn.close()
                    return jsonify({'success': False, 'message': 'Ungültige Gruppe'}), 400

            # Wenn Gruppen-Status entfernt wird, prüfen ob noch Kinder vorhanden
            if not is_group:
                children_count = conn.execute(
                    'SELECT COUNT(*) as count FROM items WHERE group_id = ? AND organization_id = ?',
                    (id, organization_id)
                ).fetchone()['count']
                if children_count > 0:
                    conn.close()
                    return jsonify({'success': False, 'message': f'Diese Gruppe enthält noch {children_count} Artikel. Bitte erst Artikel entfernen.'}), 400

            conn.execute('''UPDATE items SET
                sku = ?, name = ?, barcode = ?, description = ?, category_id = ?, location_id = ?,
                quantity = ?, min_quantity = ?, unit = ?, price = ?, supplier = ?,
                notes = ?, requires_maintenance = ?, maintenance_interval_days = ?,
                last_maintenance_date = ?, next_maintenance_date = ?, maintenance_notes = ?,
                is_group = ?, group_id = ?,
                updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND organization_id = ?''',
                (data.get('sku'), data['name'], barcode, data.get('description'),
                 data.get('category_id'), data.get('location_id'),
                 data.get('quantity', 0), data.get('min_quantity', 0),
                 data.get('unit', 'Stück'), data.get('price', 0.0),
                 data.get('supplier'), data.get('notes'),
                 data.get('requires_maintenance', False),
                 data.get('maintenance_interval_days'),
                 data.get('last_maintenance_date'),
                 data.get('next_maintenance_date'),
                 data.get('maintenance_notes'),
                 is_group, group_id,
                 id, organization_id))
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'message': 'Artikel aktualisiert'})

        item = conn.execute('''SELECT i.*, c.name as category_name, l.name as location_name,
                                     g.name as group_name
                              FROM items i
                              LEFT JOIN categories c ON i.category_id = c.id
                              LEFT JOIN locations l ON i.location_id = l.id
                              LEFT JOIN items g ON i.group_id = g.id
                              WHERE i.id = ? AND i.organization_id = ?''', (id, organization_id)).fetchone()
        conn.close()
        return jsonify(dict(item) if item else {})
    except Exception as e:
        print(f"ERROR in item endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# ============= BEWEGUNGEN =============

@app.route('/api/items/<int:id>/move', methods=['POST'])
@login_required
@csrf_protect_api()
def move_item(id):
    """Einbuchen oder Ausbuchen von Artikeln"""
    conn = get_db_connection()
    data = request.json

    move_type = data['type']  # 'in' oder 'out'
    quantity = int(data['quantity'])
    organization_id = session.get('organization_id')
    user_id = session.get('user_id')

    # Aktuellen Bestand holen
    item = conn.execute('SELECT quantity FROM items WHERE id = ?', (id,)).fetchone()
    if not item:
        conn.close()
        return jsonify({'success': False, 'message': 'Artikel nicht gefunden'}), 404

    current_qty = item['quantity']

    if move_type == 'in':
        new_qty = current_qty + quantity
    else:  # out
        if current_qty < quantity:
            conn.close()
            return jsonify({'success': False, 'message': 'Nicht genügend Bestand'}), 400
        new_qty = current_qty - quantity

    # Bestand aktualisieren
    conn.execute('UPDATE items SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (new_qty, id))

    slip_id = None
    # Bei Ausbuchung automatisch Entnahmeschein erstellen
    if move_type == 'out':
        cursor = conn.execute(
            '''INSERT INTO withdrawal_slips (organization_id, user_id, reference, notes)
               VALUES (?, ?, ?, ?)''',
            (organization_id, user_id, data.get('reference'), data.get('notes'))
        )
        slip_id = cursor.lastrowid

    # Bewegung protokollieren
    conn.execute(
        '''INSERT INTO movements (item_id, user_id, type, quantity, reference, notes, slip_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (id, user_id, move_type, quantity, data.get('reference'), data.get('notes'), slip_id)
    )

    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'Bewegung gebucht', 'new_quantity': new_qty, 'slip_id': slip_id})


@app.route('/api/withdrawals/batch', methods=['POST'])
@login_required
@csrf_protect_api()
def create_batch_withdrawal():
    """Sammelentnahme: mehrere Artikel auf einmal ausbuchen und einen gemeinsamen Schein erstellen"""
    conn = get_db_connection()
    data = request.json
    items_list = data.get('items', [])
    organization_id = session.get('organization_id')
    user_id = session.get('user_id')

    if not items_list:
        conn.close()
        return jsonify({'success': False, 'message': 'Keine Artikel angegeben'}), 400

    # Vorab alle Bestände prüfen
    for entry in items_list:
        item = conn.execute(
            'SELECT quantity FROM items WHERE id = ? AND organization_id = ?',
            (entry['item_id'], organization_id)
        ).fetchone()
        if not item:
            conn.close()
            return jsonify({'success': False, 'message': f'Artikel {entry["item_id"]} nicht gefunden'}), 404
        if item['quantity'] < int(entry['quantity']):
            conn.close()
            return jsonify({'success': False, 'message': f'Nicht genügend Bestand für Artikel {entry["item_id"]}'}), 400

    # Sammelschein anlegen
    cursor = conn.execute(
        '''INSERT INTO withdrawal_slips (organization_id, user_id, reference, notes)
           VALUES (?, ?, ?, ?)''',
        (organization_id, user_id, data.get('reference'), data.get('notes'))
    )
    slip_id = cursor.lastrowid

    # Alle Positionen ausbuchen
    for entry in items_list:
        item_id = int(entry['item_id'])
        quantity = int(entry['quantity'])
        conn.execute(
            'UPDATE items SET quantity = quantity - ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (quantity, item_id)
        )
        conn.execute(
            '''INSERT INTO movements (item_id, user_id, type, quantity, reference, notes, slip_id)
               VALUES (?, ?, 'out', ?, ?, ?, ?)''',
            (item_id, user_id, quantity, data.get('reference'), entry.get('notes'), slip_id)
        )

    conn.commit()
    conn.close()
    return jsonify({'success': True, 'slip_id': slip_id})


@app.route('/slip/<int:slip_id>')
@login_required
def print_slip(slip_id):
    """Entnahmeschein drucken"""
    organization_id = session.get('organization_id')
    conn = get_db_connection()

    slip = conn.execute(
        '''SELECT ws.*, u.first_name || ' ' || u.last_name AS user_name, u.username,
                  o.name AS org_name
           FROM withdrawal_slips ws
           LEFT JOIN users u ON ws.user_id = u.id
           LEFT JOIN organizations o ON ws.organization_id = o.id
           WHERE ws.id = ? AND ws.organization_id = ?''',
        (slip_id, organization_id)
    ).fetchone()

    if not slip:
        conn.close()
        return 'Entnahmeschein nicht gefunden', 404

    movements = conn.execute(
        '''SELECT m.quantity, m.notes,
                  i.name AS item_name, i.sku, i.unit,
                  l.name AS location_name
           FROM movements m
           JOIN items i ON m.item_id = i.id
           LEFT JOIN locations l ON i.location_id = l.id
           WHERE m.slip_id = ?
           ORDER BY m.id''',
        (slip_id,)
    ).fetchall()

    conn.close()
    return render_template('entnahmeschein.html',
                           slip=dict(slip),
                           movements=[dict(m) for m in movements])

@app.route('/api/items/<int:id>/movements')
@login_required
def item_movements(id):
    """Bewegungshistorie eines Artikels"""
    conn = get_db_connection()
    movements = conn.execute('''SELECT * FROM movements 
                               WHERE item_id = ? 
                               ORDER BY created_at DESC''', (id,)).fetchall()
    conn.close()
    return jsonify([dict(mov) for mov in movements])

# ============= GOOGLE DRIVE SYNC =============

@app.route('/api/sync/manual', methods=['POST'])
@login_required
@csrf_protect_api()
def manual_sync():
    """Manueller Sync zu Google Drive"""
    try:
        # Versuche Google Drive Sync
        result = sync_to_google_drive()
        
        if result['success']:
            # Sync Log aktualisieren
            conn = get_db_connection()
            conn.execute('INSERT INTO sync_log (status, message) VALUES (?, ?)',
                        ('success', result['message']))
            conn.commit()
            conn.close()
            
            return jsonify(result)
        else:
            # Bei Fehler: Lokales Backup erstellen
            if not os.path.exists(BACKUP_FOLDER):
                os.makedirs(BACKUP_FOLDER)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = f'{BACKUP_FOLDER}/inventory_backup_{timestamp}.db'
            
            import shutil
            shutil.copy2(DB_PATH, backup_path)
            
            # Sync Log aktualisieren
            conn = get_db_connection()
            conn.execute('INSERT INTO sync_log (status, message) VALUES (?, ?)',
                        ('fallback', f'Lokales Backup erstellt: {backup_path}'))
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': f'Google Drive nicht verfügbar. Lokales Backup erstellt: {backup_path}',
                'fallback': True,
                'backup_path': backup_path
            })
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sync/status')
@login_required
def sync_status_route():
    """Sync Status abfragen (inkl. Auto-Backup-Status)"""
    try:
        from auto_backup import get_backup_service
        backup_service = get_backup_service()
        auto_backup_status = backup_service.get_status()
    except:
        auto_backup_status = {'is_running': False, 'error': 'Service nicht verfügbar'}

    return jsonify({
        **sync_status,
        'auto_backup': auto_backup_status
    })

@app.route('/api/backup/status')
@login_required
def backup_status():
    """Auto-Backup-Status abfragen"""
    try:
        from auto_backup import get_backup_service
        backup_service = get_backup_service()
        return jsonify(backup_service.get_status())
    except Exception as e:
        return jsonify({
            'is_running': False,
            'error': str(e)
        }), 500

@app.route('/api/backup/manual', methods=['POST'])
@login_required
@csrf_protect_api()
def trigger_manual_backup():
    """Manuelles Backup auslösen"""
    try:
        from auto_backup import get_backup_service
        backup_service = get_backup_service()
        result = backup_service.manual_backup()
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/backup/list')
@login_required
def list_backups():
    """Liste alle verfügbaren Backups"""
    try:
        from gdrive_sync import GoogleDriveSync
        sync = GoogleDriveSync()
        sync.authenticate()
        backups = sync.list_backups(limit=50)

        return jsonify({
            'success': True,
            'backups': backups
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/backup/restore/<file_id>', methods=['POST'])
@admin_required
@csrf_protect_api()
def restore_backup(file_id):
    """Stellt ein Backup wieder her"""
    try:
        from gdrive_sync import GoogleDriveSync
        import shutil
        from datetime import datetime

        # Erstelle Backup der aktuellen DB vor Wiederherstellung
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        current_backup = f'inventory_before_restore_{timestamp}.db'
        shutil.copy(DB_PATH, os.path.join(BACKUP_FOLDER, current_backup))

        # Lade Backup von Google Drive herunter
        sync = GoogleDriveSync()
        sync.authenticate()

        temp_file = 'temp_restore.db'
        sync.download_backup(file_id, temp_file)

        # Ersetze aktuelle Datenbank
        shutil.move(temp_file, DB_PATH)

        return jsonify({
            'success': True,
            'message': 'Backup erfolgreich wiederhergestellt',
            'backup_before_restore': current_backup
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/backup/download/<file_id>')
@admin_required
def download_backup(file_id):
    """Lädt ein Backup herunter"""
    try:
        from gdrive_sync import GoogleDriveSync

        sync = GoogleDriveSync()
        sync.authenticate()

        # Download in temp file
        temp_file = 'temp_download.db'
        sync.download_backup(file_id, temp_file)

        return send_file(temp_file,
                        as_attachment=True,
                        download_name=f'stockmaster_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/export/csv')
@login_required
def export_csv():
    """Export aller Artikel als CSV"""
    import csv
    from io import StringIO
    
    conn = get_db_connection()
    items = conn.execute('''SELECT i.*, c.name as category_name, l.name as location_name
                           FROM items i
                           LEFT JOIN categories c ON i.category_id = c.id
                           LEFT JOIN locations l ON i.location_id = l.id
                           ORDER BY i.name''').fetchall()
    conn.close()
    
    si = StringIO()
    writer = csv.writer(si)
    
    # Header
    writer.writerow(['SKU', 'Name', 'Beschreibung', 'Kategorie', 'Standort', 
                    'Menge', 'Einheit', 'Mindestbestand', 'Preis', 'Lieferant'])
    
    # Daten
    for item in items:
        writer.writerow([
            item['sku'] or '', item['name'], item['description'] or '',
            item['category_name'] or '', item['location_name'] or '',
            item['quantity'], item['unit'], item['min_quantity'],
            item['price'], item['supplier'] or ''
        ])
    
    output = si.getvalue()
    si.close()
    
    from flask import Response
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=inventory_export.csv"})

# ============= QR-CODE ROUTES =============

@app.route('/api/items/<int:id>/qrcode')
@login_required
def get_item_qrcode(id):
    """Gibt den QR-Code für ein Item zurück"""
    conn = get_db_connection()
    item = conn.execute('SELECT * FROM items WHERE id = ?', (id,)).fetchone()
    conn.close()
    
    if not item:
        return jsonify({'success': False, 'message': 'Artikel nicht gefunden'}), 404
    
    item_data = dict(item)
    buffer = generate_qr_code(id, item_data)
    
    return send_file(buffer, mimetype='image/png')

@app.route('/api/items/<int:id>/qrcode-base64')
@login_required
def get_item_qrcode_base64(id):
    """Gibt den QR-Code als Base64 String zurück"""
    conn = get_db_connection()
    item = conn.execute('SELECT * FROM items WHERE id = ?', (id,)).fetchone()
    conn.close()

    if not item:
        return jsonify({'success': False, 'message': 'Artikel nicht gefunden'}), 404

    item_data = dict(item)
    qr_base64 = generate_qr_code_base64(id, item_data)

    return jsonify({'success': True, 'qrcode': qr_base64})

# ============= BARCODE ROUTES =============

@app.route('/api/items/<int:id>/barcode')
@login_required
def get_item_barcode(id):
    """Gibt den Barcode für ein Item zurück"""
    conn = get_db_connection()
    item = conn.execute('SELECT * FROM items WHERE id = ?', (id,)).fetchone()
    conn.close()

    if not item:
        return jsonify({'success': False, 'message': 'Artikel nicht gefunden'}), 404

    item_data = dict(item)
    buffer = generate_barcode(id, item_data)

    return send_file(buffer, mimetype='image/png')

@app.route('/api/items/<int:id>/barcode-base64')
@login_required
def get_item_barcode_base64(id):
    """Gibt den Barcode als Base64 String zurück"""
    conn = get_db_connection()
    item = conn.execute('SELECT * FROM items WHERE id = ?', (id,)).fetchone()
    conn.close()

    if not item:
        return jsonify({'success': False, 'message': 'Artikel nicht gefunden'}), 404

    item_data = dict(item)
    barcode_base64 = generate_barcode_base64(id, item_data)

    return jsonify({'success': True, 'barcode': barcode_base64})

@app.route('/api/items/search-barcode', methods=['GET'])
@login_required
def search_item_by_barcode():
    """Sucht einen Artikel anhand seines Barcodes (externe Barcodes oder ITEM-Codes)"""
    barcode = request.args.get('barcode', '').strip()
    organization_id = session.get('organization_id')

    if not barcode:
        return jsonify({'success': False, 'message': 'Kein Barcode angegeben'}), 400

    conn = get_db_connection()

    # Suche 1: Prüfe ob es ein ITEM-Code ist (z.B. ITEM00000001)
    if barcode.startswith('ITEM'):
        try:
            item_id = int(barcode.replace('ITEM', '').lstrip('0'))
            item = conn.execute(
                'SELECT * FROM items WHERE id = ? AND organization_id = ?',
                (item_id, organization_id)
            ).fetchone()
            if item:
                conn.close()
                return jsonify({'success': True, 'item': dict(item)})
        except:
            pass

    # Suche 2: Suche nach externem Barcode in der barcode-Spalte
    item = conn.execute(
        'SELECT * FROM items WHERE barcode = ? AND organization_id = ?',
        (barcode, organization_id)
    ).fetchone()

    conn.close()

    if item:
        return jsonify({'success': True, 'item': dict(item)})
    else:
        return jsonify({
            'success': False,
            'message': 'Artikel nicht gefunden',
            'barcode': barcode,
            'suggest_create': True  # Frontend kann anbieten, neuen Artikel anzulegen
        }), 404

@app.route('/api/items/<int:id>/upload-image', methods=['POST'])
@login_required
@csrf_protect_api()
def upload_item_image(id):
    """Lädt ein Bild für einen Artikel hoch"""
    conn = get_db_connection()
    organization_id = session.get('organization_id')

    # Prüfe ob Artikel existiert und zur Organisation gehört
    item = conn.execute('''SELECT * FROM items
                          WHERE id = ? AND organization_id = ?''',
                       (id, organization_id)).fetchone()

    if not item:
        conn.close()
        return jsonify({'success': False, 'message': 'Artikel nicht gefunden'}), 404

    # Prüfe ob Datei hochgeladen wurde
    if 'image' not in request.files:
        conn.close()
        return jsonify({'success': False, 'message': 'Keine Datei hochgeladen'}), 400

    file = request.files['image']

    # Prüfe ob Dateiname leer ist
    if file.filename == '':
        conn.close()
        return jsonify({'success': False, 'message': 'Keine Datei ausgewählt'}), 400

    # Prüfe Dateityp
    if not allowed_file(file.filename):
        conn.close()
        return jsonify({
            'success': False,
            'message': f'Ungültiger Dateityp. Erlaubt: {", ".join(ALLOWED_EXTENSIONS)}'
        }), 400

    # Prüfe Dateigröße (wird durch MAX_CONTENT_LENGTH automatisch geprüft, aber zusätzliche Validierung)
    file.seek(0, os.SEEK_END)
    file_length = file.tell()
    file.seek(0)  # Reset file pointer

    if file_length > app.config['MAX_CONTENT_LENGTH']:
        conn.close()
        return jsonify({
            'success': False,
            'message': f'Datei zu groß. Maximum: 5MB'
        }), 400

    try:
        # Lösche altes Bild falls vorhanden
        if item['image_path']:
            old_path = os.path.join(UPLOAD_FOLDER, item['image_path'])
            if os.path.exists(old_path):
                os.remove(old_path)

        # Speichere neue Datei
        filename = secure_filename_custom(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        # Aktualisiere Datenbank
        conn.execute('''UPDATE items
                       SET image_path = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE id = ?''',
                    (filename, id))
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Bild erfolgreich hochgeladen',
            'image_path': filename,
            'image_url': f'/static/uploads/items/{filename}'
        })

    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': f'Fehler beim Upload: {str(e)}'}), 500

@app.route('/api/items/<int:id>/delete-image', methods=['DELETE'])
@login_required
@csrf_protect_api()
def delete_item_image(id):
    """Löscht das Bild eines Artikels"""
    conn = get_db_connection()
    organization_id = session.get('organization_id')

    # Prüfe ob Artikel existiert und zur Organisation gehört
    item = conn.execute('''SELECT * FROM items
                          WHERE id = ? AND organization_id = ?''',
                       (id, organization_id)).fetchone()

    if not item:
        conn.close()
        return jsonify({'success': False, 'message': 'Artikel nicht gefunden'}), 404

    if not item['image_path']:
        conn.close()
        return jsonify({'success': False, 'message': 'Kein Bild vorhanden'}), 404

    try:
        # Lösche Datei
        filepath = os.path.join(UPLOAD_FOLDER, item['image_path'])
        if os.path.exists(filepath):
            os.remove(filepath)

        # Aktualisiere Datenbank
        conn.execute('''UPDATE items
                       SET image_path = NULL, updated_at = CURRENT_TIMESTAMP
                       WHERE id = ?''', (id,))
        conn.commit()
        conn.close()

        return jsonify({'success': True, 'message': 'Bild erfolgreich gelöscht'})

    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': f'Fehler beim Löschen: {str(e)}'}), 500

# ============================================================
# WARTUNGSMANAGEMENT API
# ============================================================

# --- Wartungstypen CRUD ---

@app.route('/api/maintenance/types', methods=['GET', 'POST'])
@login_required
def maintenance_types_api():
    """CRUD für Wartungstypen"""
    conn = get_db_connection()
    organization_id = session.get('organization_id')

    if request.method == 'POST':
        data = request.json
        name = sanitize_string(data.get('name'), 100)
        if not name:
            conn.close()
            return jsonify({'success': False, 'message': 'Name ist erforderlich'}), 400

        try:
            cursor = conn.execute('''INSERT INTO maintenance_types
                (organization_id, name, description, color, icon, default_interval_days)
                VALUES (?, ?, ?, ?, ?, ?)''',
                (organization_id, name,
                 sanitize_string(data.get('description'), 500),
                 data.get('color', '#6366f1'),
                 data.get('icon', 'wrench'),
                 data.get('default_interval_days')))
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'message': 'Wartungstyp erstellt', 'id': cursor.lastrowid})
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({'success': False, 'message': 'Ein Wartungstyp mit diesem Namen existiert bereits'}), 400

    types = conn.execute('''SELECT * FROM maintenance_types
                           WHERE organization_id = ? AND is_active = 1
                           ORDER BY name''', (organization_id,)).fetchall()
    conn.close()
    return jsonify([dict(t) for t in types])

@app.route('/api/maintenance/types/<int:type_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
@csrf_protect_api()
def maintenance_type_detail(type_id):
    """Einzelnen Wartungstyp abrufen, bearbeiten oder löschen"""
    conn = get_db_connection()
    organization_id = session.get('organization_id')

    mt = conn.execute('SELECT * FROM maintenance_types WHERE id = ? AND organization_id = ?',
                      (type_id, organization_id)).fetchone()
    if not mt:
        conn.close()
        return jsonify({'success': False, 'message': 'Wartungstyp nicht gefunden'}), 404

    if request.method == 'DELETE':
        conn.execute('UPDATE maintenance_types SET is_active = 0 WHERE id = ?', (type_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Wartungstyp deaktiviert'})

    if request.method == 'PUT':
        data = request.json
        conn.execute('''UPDATE maintenance_types SET
            name = ?, description = ?, color = ?, icon = ?, default_interval_days = ?
            WHERE id = ? AND organization_id = ?''',
            (sanitize_string(data.get('name'), 100),
             sanitize_string(data.get('description'), 500),
             data.get('color', mt['color']),
             data.get('icon', mt['icon']),
             data.get('default_interval_days'),
             type_id, organization_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Wartungstyp aktualisiert'})

    conn.close()
    return jsonify(dict(mt))

# --- Wartungspläne (Schedules) ---

@app.route('/api/maintenance/schedules/<int:item_id>', methods=['GET', 'POST'])
@login_required
def item_schedules_api(item_id):
    """Wartungspläne eines Artikels abrufen oder hinzufügen"""
    conn = get_db_connection()
    organization_id = session.get('organization_id')

    item = conn.execute('SELECT id FROM items WHERE id = ? AND organization_id = ?',
                        (item_id, organization_id)).fetchone()
    if not item:
        conn.close()
        return jsonify({'success': False, 'message': 'Artikel nicht gefunden'}), 404

    if request.method == 'POST':
        data = request.json
        type_id = data.get('maintenance_type_id')
        interval_days = data.get('interval_days')

        if not type_id or not interval_days:
            conn.close()
            return jsonify({'success': False, 'message': 'Wartungstyp und Intervall sind erforderlich'}), 400

        next_date = data.get('next_date')
        if not next_date and interval_days:
            next_date = (datetime.now() + timedelta(days=int(interval_days))).strftime('%Y-%m-%d')

        try:
            cursor = conn.execute('''INSERT INTO item_maintenance_schedules
                (item_id, maintenance_type_id, interval_days, last_date, next_date,
                 assigned_user_id, priority, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (item_id, type_id, interval_days,
                 data.get('last_date'), next_date,
                 data.get('assigned_user_id'),
                 data.get('priority', 'normal'),
                 sanitize_string(data.get('notes'), 1000)))
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'message': 'Wartungsplan hinzugefügt', 'id': cursor.lastrowid})
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({'success': False, 'message': 'Dieser Wartungstyp ist bereits für diesen Artikel konfiguriert'}), 400

    schedules = conn.execute('''
        SELECT ims.*, mt.name as type_name, mt.color as type_color, mt.icon as type_icon,
               u.username as assigned_username
        FROM item_maintenance_schedules ims
        JOIN maintenance_types mt ON ims.maintenance_type_id = mt.id
        LEFT JOIN users u ON ims.assigned_user_id = u.id
        WHERE ims.item_id = ? AND ims.is_active = 1
        ORDER BY ims.next_date ASC
    ''', (item_id,)).fetchall()
    conn.close()
    return jsonify([dict(s) for s in schedules])

@app.route('/api/maintenance/schedules/entry/<int:schedule_id>', methods=['PUT', 'DELETE'])
@login_required
@csrf_protect_api()
def schedule_entry_api(schedule_id):
    """Einzelnen Wartungsplan bearbeiten oder entfernen"""
    conn = get_db_connection()
    organization_id = session.get('organization_id')

    schedule = conn.execute('''
        SELECT ims.* FROM item_maintenance_schedules ims
        JOIN items i ON ims.item_id = i.id
        WHERE ims.id = ? AND i.organization_id = ?
    ''', (schedule_id, organization_id)).fetchone()

    if not schedule:
        conn.close()
        return jsonify({'success': False, 'message': 'Wartungsplan nicht gefunden'}), 404

    if request.method == 'DELETE':
        conn.execute('UPDATE item_maintenance_schedules SET is_active = 0 WHERE id = ?', (schedule_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Wartungsplan entfernt'})

    data = request.json
    conn.execute('''UPDATE item_maintenance_schedules SET
        interval_days = ?, next_date = ?, assigned_user_id = ?,
        priority = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?''',
        (data.get('interval_days', schedule['interval_days']),
         data.get('next_date', schedule['next_date']),
         data.get('assigned_user_id', schedule['assigned_user_id']),
         data.get('priority', schedule['priority']),
         sanitize_string(data.get('notes'), 1000),
         schedule_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Wartungsplan aktualisiert'})

@app.route('/api/maintenance/schedules/entry/<int:schedule_id>/assign', methods=['PUT'])
@login_required
@csrf_protect_api()
def assign_schedule(schedule_id):
    """Benutzer einem Wartungsplan zuweisen"""
    conn = get_db_connection()
    organization_id = session.get('organization_id')
    data = request.json

    schedule = conn.execute('''
        SELECT ims.* FROM item_maintenance_schedules ims
        JOIN items i ON ims.item_id = i.id
        WHERE ims.id = ? AND i.organization_id = ?
    ''', (schedule_id, organization_id)).fetchone()

    if not schedule:
        conn.close()
        return jsonify({'success': False, 'message': 'Wartungsplan nicht gefunden'}), 404

    conn.execute('UPDATE item_maintenance_schedules SET assigned_user_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                 (data.get('assigned_user_id'), schedule_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Benutzer zugewiesen'})

# --- Fällige Wartungen (Übersicht) ---

@app.route('/api/maintenance/due')
@login_required
def get_due_maintenance():
    """Gibt alle fälligen Wartungen zurück (basierend auf Wartungsplänen)"""
    conn = get_db_connection()
    organization_id = session.get('organization_id')

    warning_days = request.args.get('warning_days', 30, type=int)
    type_id = request.args.get('type_id', type=int)
    assigned_user_id = request.args.get('assigned_user_id', type=int)
    status_filter = request.args.get('status')

    warning_date = (datetime.now() + timedelta(days=warning_days)).strftime('%Y-%m-%d')
    today = datetime.now().strftime('%Y-%m-%d')

    query = '''
        SELECT ims.id as schedule_id, ims.interval_days, ims.last_date, ims.next_date,
               ims.priority, ims.notes as schedule_notes, ims.assigned_user_id,
               i.id as item_id, i.name as item_name, i.sku, i.image_path,
               mt.id as type_id, mt.name as type_name, mt.color as type_color, mt.icon as type_icon,
               c.name as category_name, l.name as location_name,
               u.username as assigned_username,
               CASE
                   WHEN ims.next_date <= ? THEN 'overdue'
                   WHEN ims.next_date <= ? THEN 'due_soon'
                   ELSE 'ok'
               END as maintenance_status,
               julianday(ims.next_date) - julianday('now') as days_until_maintenance
        FROM item_maintenance_schedules ims
        JOIN items i ON ims.item_id = i.id
        JOIN maintenance_types mt ON ims.maintenance_type_id = mt.id
        LEFT JOIN categories c ON i.category_id = c.id
        LEFT JOIN locations l ON i.location_id = l.id
        LEFT JOIN users u ON ims.assigned_user_id = u.id
        WHERE ims.is_active = 1
        AND i.organization_id = ?
        AND ims.next_date IS NOT NULL
        AND ims.next_date <= ?
    '''
    params = [today, warning_date, organization_id, warning_date]

    if type_id:
        query += ' AND mt.id = ?'
        params.append(type_id)
    if assigned_user_id:
        query += ' AND ims.assigned_user_id = ?'
        params.append(assigned_user_id)

    query += ' ORDER BY ims.next_date ASC'

    items = conn.execute(query, params).fetchall()
    result = [dict(item) for item in items]

    if status_filter and status_filter != 'all':
        result = [r for r in result if r['maintenance_status'] == status_filter]

    conn.close()
    return jsonify(result)

@app.route('/api/maintenance/my-tasks')
@login_required
def get_my_maintenance_tasks():
    """Gibt dem aktuellen Benutzer zugewiesene Wartungen zurück"""
    conn = get_db_connection()
    user_id = session.get('user_id')
    organization_id = session.get('organization_id')
    today = datetime.now().strftime('%Y-%m-%d')

    tasks = conn.execute('''
        SELECT ims.id as schedule_id, ims.interval_days, ims.last_date, ims.next_date,
               ims.priority, ims.notes as schedule_notes,
               i.id as item_id, i.name as item_name, i.sku,
               mt.name as type_name, mt.color as type_color, mt.icon as type_icon,
               c.name as category_name, l.name as location_name,
               CASE
                   WHEN ims.next_date <= ? THEN 'overdue'
                   ELSE 'due_soon'
               END as maintenance_status,
               julianday(ims.next_date) - julianday('now') as days_until_maintenance
        FROM item_maintenance_schedules ims
        JOIN items i ON ims.item_id = i.id
        JOIN maintenance_types mt ON ims.maintenance_type_id = mt.id
        LEFT JOIN categories c ON i.category_id = c.id
        LEFT JOIN locations l ON i.location_id = l.id
        WHERE ims.assigned_user_id = ?
        AND ims.is_active = 1
        AND i.organization_id = ?
        ORDER BY ims.next_date ASC
    ''', (today, user_id, organization_id)).fetchall()

    conn.close()
    return jsonify([dict(t) for t in tasks])

@app.route('/api/maintenance/calendar')
@login_required
def get_maintenance_calendar():
    """Gibt alle Wartungstermine in einem Datumsbereich zurück"""
    conn = get_db_connection()
    organization_id = session.get('organization_id')

    start = request.args.get('start', datetime.now().strftime('%Y-%m-01'))
    end_default = (datetime.now().replace(day=1) + timedelta(days=32)).replace(day=1).strftime('%Y-%m-%d')
    end = request.args.get('end', end_default)

    events = conn.execute('''
        SELECT ims.id as schedule_id, ims.next_date, ims.priority,
               i.id as item_id, i.name as item_name,
               mt.name as type_name, mt.color as type_color,
               CASE WHEN ims.next_date <= date('now') THEN 'overdue' ELSE 'upcoming' END as status
        FROM item_maintenance_schedules ims
        JOIN items i ON ims.item_id = i.id
        JOIN maintenance_types mt ON ims.maintenance_type_id = mt.id
        WHERE ims.is_active = 1
        AND i.organization_id = ?
        AND ims.next_date BETWEEN ? AND ?
        ORDER BY ims.next_date ASC
    ''', (organization_id, start, end)).fetchall()

    conn.close()
    return jsonify([dict(e) for e in events])

# --- Wartung abschließen (erweitert) ---

@app.route('/api/maintenance/complete/<int:schedule_id>', methods=['POST'])
@login_required
@csrf_protect_api()
def complete_maintenance(schedule_id):
    """Schließt eine Wartung ab (mit Checkliste und Kosten)"""
    conn = get_db_connection()
    organization_id = session.get('organization_id')
    data = request.json

    schedule = conn.execute('''
        SELECT ims.*, i.id as item_id, i.organization_id, mt.name as type_name
        FROM item_maintenance_schedules ims
        JOIN items i ON ims.item_id = i.id
        JOIN maintenance_types mt ON ims.maintenance_type_id = mt.id
        WHERE ims.id = ? AND i.organization_id = ?
    ''', (schedule_id, organization_id)).fetchone()

    if not schedule:
        conn.close()
        return jsonify({'success': False, 'message': 'Wartungsplan nicht gefunden'}), 404

    maintenance_date = data.get('maintenance_date', datetime.now().strftime('%Y-%m-%d'))
    notes = data.get('notes', '')
    performed_by = session.get('username')
    user_id = session.get('user_id')

    # Kosten
    cost_parts = float(data.get('cost_parts', 0) or 0)
    cost_labor = float(data.get('cost_labor', 0) or 0)
    cost = cost_parts + cost_labor
    cost_notes = sanitize_string(data.get('cost_notes'), 500)

    # Berechne nächstes Wartungsdatum
    maintenance_dt = datetime.strptime(maintenance_date, '%Y-%m-%d')
    next_maintenance = (maintenance_dt + timedelta(days=schedule['interval_days'])).strftime('%Y-%m-%d')

    # Aktualisiere Schedule
    conn.execute('''UPDATE item_maintenance_schedules SET
        last_date = ?, next_date = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?''', (maintenance_date, next_maintenance, schedule_id))

    # Aktualisiere auch die alten Felder auf dem Item (Rückwärtskompatibilität)
    conn.execute('''UPDATE items SET
        last_maintenance_date = ?, next_maintenance_date = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?''', (maintenance_date, next_maintenance, schedule['item_id']))

    # Erstelle Historien-Eintrag
    cursor = conn.execute('''INSERT INTO maintenance_history
        (item_id, user_id, maintenance_date, performed_by, notes, next_maintenance_date,
         maintenance_type_id, schedule_id, cost, cost_parts, cost_labor, cost_notes, organization_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (schedule['item_id'], user_id, maintenance_date, performed_by, notes, next_maintenance,
         schedule['maintenance_type_id'], schedule_id, cost, cost_parts, cost_labor, cost_notes,
         organization_id))

    history_id = cursor.lastrowid

    # Checklisten-Ergebnisse speichern
    checklist_results = data.get('checklist_results', [])
    for result in checklist_results:
        conn.execute('''INSERT INTO maintenance_checklist_results
            (maintenance_history_id, checklist_item_id, is_checked, notes)
            VALUES (?, ?, ?, ?)''',
            (history_id, result.get('checklist_item_id'),
             result.get('is_checked', False),
             sanitize_string(result.get('notes'), 500)))

    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'message': 'Wartung erfolgreich abgeschlossen',
        'next_maintenance_date': next_maintenance,
        'history_id': history_id
    })

# --- Wartungshistorie (erweitert) ---

@app.route('/api/maintenance/history/<int:item_id>')
@login_required
def get_maintenance_history(item_id):
    """Gibt die erweiterte Wartungshistorie eines Artikels zurück"""
    conn = get_db_connection()
    organization_id = session.get('organization_id')

    history = conn.execute('''
        SELECT mh.*, mt.name as type_name, mt.color as type_color
        FROM maintenance_history mh
        LEFT JOIN maintenance_types mt ON mh.maintenance_type_id = mt.id
        WHERE mh.item_id = ?
        AND (mh.organization_id = ? OR mh.organization_id IS NULL)
        ORDER BY mh.maintenance_date DESC
    ''', (item_id, organization_id)).fetchall()

    result = []
    for h in history:
        entry = dict(h)
        # Checklisten-Ergebnisse laden
        if h['id']:
            checklist = conn.execute('''
                SELECT mcr.*, ci.description as item_description, ci.is_required
                FROM maintenance_checklist_results mcr
                JOIN checklist_items ci ON mcr.checklist_item_id = ci.id
                WHERE mcr.maintenance_history_id = ?
            ''', (h['id'],)).fetchall()
            entry['checklist_results'] = [dict(c) for c in checklist]
        result.append(entry)

    conn.close()
    return jsonify(result)

# --- Checklisten ---

@app.route('/api/maintenance/checklists/<int:type_id>', methods=['GET', 'POST'])
@login_required
def maintenance_checklists_api(type_id):
    """Checkliste eines Wartungstyps abrufen oder erstellen/aktualisieren"""
    conn = get_db_connection()
    organization_id = session.get('organization_id')

    mt = conn.execute('SELECT id FROM maintenance_types WHERE id = ? AND organization_id = ?',
                      (type_id, organization_id)).fetchone()
    if not mt:
        conn.close()
        return jsonify({'success': False, 'message': 'Wartungstyp nicht gefunden'}), 404

    if request.method == 'POST':
        data = request.json
        checklist_name = sanitize_string(data.get('name', 'Standard-Checkliste'), 200)
        items_data = data.get('items', [])

        # Bestehende Checkliste suchen oder erstellen
        existing = conn.execute('''SELECT id FROM maintenance_checklists
                                  WHERE maintenance_type_id = ? AND organization_id = ?''',
                               (type_id, organization_id)).fetchone()

        if existing:
            checklist_id = existing['id']
            conn.execute('UPDATE maintenance_checklists SET name = ? WHERE id = ?',
                        (checklist_name, checklist_id))
            conn.execute('DELETE FROM checklist_items WHERE checklist_id = ?', (checklist_id,))
        else:
            cursor = conn.execute('''INSERT INTO maintenance_checklists
                (maintenance_type_id, organization_id, name)
                VALUES (?, ?, ?)''', (type_id, organization_id, checklist_name))
            checklist_id = cursor.lastrowid

        for idx, item in enumerate(items_data):
            conn.execute('''INSERT INTO checklist_items
                (checklist_id, description, sort_order, is_required)
                VALUES (?, ?, ?, ?)''',
                (checklist_id, sanitize_string(item.get('description'), 500),
                 idx, item.get('is_required', False)))

        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Checkliste gespeichert', 'id': checklist_id})

    # GET: Checkliste laden
    checklist = conn.execute('''SELECT mc.*, ci.id as item_id, ci.description, ci.sort_order, ci.is_required
        FROM maintenance_checklists mc
        LEFT JOIN checklist_items ci ON mc.id = ci.checklist_id
        WHERE mc.maintenance_type_id = ? AND mc.organization_id = ?
        ORDER BY ci.sort_order ASC
    ''', (type_id, organization_id)).fetchall()

    if not checklist:
        conn.close()
        return jsonify({'id': None, 'name': None, 'items': []})

    result = {
        'id': checklist[0]['id'],
        'name': checklist[0]['name'],
        'items': [{'id': c['item_id'], 'description': c['description'],
                   'sort_order': c['sort_order'], 'is_required': bool(c['is_required'])}
                  for c in checklist if c['item_id']]
    }
    conn.close()
    return jsonify(result)

@app.route('/api/maintenance/checklist-results/<int:history_id>')
@login_required
def get_checklist_results(history_id):
    """Checklisten-Ergebnisse einer abgeschlossenen Wartung abrufen"""
    conn = get_db_connection()

    results = conn.execute('''
        SELECT mcr.*, ci.description as item_description, ci.is_required
        FROM maintenance_checklist_results mcr
        JOIN checklist_items ci ON mcr.checklist_item_id = ci.id
        WHERE mcr.maintenance_history_id = ?
        ORDER BY ci.sort_order ASC
    ''', (history_id,)).fetchall()

    conn.close()
    return jsonify([dict(r) for r in results])

# --- Wartungsstatistiken & Berichte ---

@app.route('/api/maintenance/stats')
@login_required
def get_maintenance_stats():
    """Übersichts-Statistiken zum Wartungsmanagement"""
    conn = get_db_connection()
    organization_id = session.get('organization_id')
    today = datetime.now().strftime('%Y-%m-%d')
    seven_days = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')

    overdue = conn.execute('''
        SELECT COUNT(*) as count FROM item_maintenance_schedules ims
        JOIN items i ON ims.item_id = i.id
        WHERE ims.is_active = 1 AND i.organization_id = ?
        AND ims.next_date IS NOT NULL AND ims.next_date <= ?
    ''', (organization_id, today)).fetchone()['count']

    due_soon = conn.execute('''
        SELECT COUNT(*) as count FROM item_maintenance_schedules ims
        JOIN items i ON ims.item_id = i.id
        WHERE ims.is_active = 1 AND i.organization_id = ?
        AND ims.next_date IS NOT NULL AND ims.next_date > ? AND ims.next_date <= ?
    ''', (organization_id, today, seven_days)).fetchone()['count']

    ok_count = conn.execute('''
        SELECT COUNT(*) as count FROM item_maintenance_schedules ims
        JOIN items i ON ims.item_id = i.id
        WHERE ims.is_active = 1 AND i.organization_id = ?
        AND ims.next_date IS NOT NULL AND ims.next_date > ?
    ''', (organization_id, seven_days)).fetchone()['count']

    monthly_cost = conn.execute('''
        SELECT COALESCE(SUM(cost), 0) as total FROM maintenance_history
        WHERE organization_id = ? AND maintenance_date >= ?
    ''', (organization_id, month_start)).fetchone()['total']

    # Compliance-Rate: Pünktlich abgeschlossene Wartungen der letzten 90 Tage
    ninety_days_ago = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    total_completed = conn.execute('''
        SELECT COUNT(*) as count FROM maintenance_history
        WHERE organization_id = ? AND maintenance_date >= ?
    ''', (organization_id, ninety_days_ago)).fetchone()['count']

    on_time = conn.execute('''
        SELECT COUNT(*) as count FROM maintenance_history mh
        JOIN item_maintenance_schedules ims ON mh.schedule_id = ims.id
        WHERE mh.organization_id = ? AND mh.maintenance_date >= ?
        AND mh.maintenance_date <= date(mh.next_maintenance_date, '-' || ims.interval_days || ' days', '+3 days')
    ''', (organization_id, ninety_days_ago)).fetchone()['count']

    compliance_rate = round((on_time / total_completed * 100) if total_completed > 0 else 100, 1)

    conn.close()
    return jsonify({
        'overdue': overdue,
        'due_soon': due_soon,
        'ok': ok_count,
        'monthly_cost': round(monthly_cost, 2),
        'compliance_rate': compliance_rate,
        'total_completed_90d': total_completed
    })

@app.route('/api/maintenance/cost-report')
@login_required
def get_maintenance_cost_report():
    """Kostenbericht für Wartungen"""
    conn = get_db_connection()
    organization_id = session.get('organization_id')

    period = request.args.get('period', '12')  # Monate
    group_by = request.args.get('group_by', 'month')  # month, type, item

    months_ago = (datetime.now() - timedelta(days=int(period) * 30)).strftime('%Y-%m-%d')

    if group_by == 'month':
        data = conn.execute('''
            SELECT strftime('%%Y-%%m', maintenance_date) as label,
                   SUM(cost) as total_cost, SUM(cost_parts) as parts, SUM(cost_labor) as labor,
                   COUNT(*) as count
            FROM maintenance_history
            WHERE organization_id = ? AND maintenance_date >= ?
            GROUP BY strftime('%%Y-%%m', maintenance_date)
            ORDER BY label ASC
        ''', (organization_id, months_ago)).fetchall()
    elif group_by == 'type':
        data = conn.execute('''
            SELECT COALESCE(mt.name, 'Unbekannt') as label, mt.color,
                   SUM(mh.cost) as total_cost, SUM(mh.cost_parts) as parts, SUM(mh.cost_labor) as labor,
                   COUNT(*) as count
            FROM maintenance_history mh
            LEFT JOIN maintenance_types mt ON mh.maintenance_type_id = mt.id
            WHERE mh.organization_id = ? AND mh.maintenance_date >= ?
            GROUP BY mh.maintenance_type_id
            ORDER BY total_cost DESC
        ''', (organization_id, months_ago)).fetchall()
    else:  # item
        data = conn.execute('''
            SELECT i.name as label,
                   SUM(mh.cost) as total_cost, SUM(mh.cost_parts) as parts, SUM(mh.cost_labor) as labor,
                   COUNT(*) as count
            FROM maintenance_history mh
            JOIN items i ON mh.item_id = i.id
            WHERE mh.organization_id = ? AND mh.maintenance_date >= ?
            GROUP BY mh.item_id
            ORDER BY total_cost DESC
            LIMIT 20
        ''', (organization_id, months_ago)).fetchall()

    conn.close()
    return jsonify([dict(d) for d in data])

@app.route('/api/maintenance/compliance-report')
@login_required
def get_maintenance_compliance_report():
    """Compliance-Bericht: Pünktlichkeit der Wartungen"""
    conn = get_db_connection()
    organization_id = session.get('organization_id')
    months_ago = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')

    data = conn.execute('''
        SELECT strftime('%%Y-%%m', mh.maintenance_date) as month,
               COUNT(*) as total,
               SUM(CASE WHEN mh.maintenance_date <= mh.next_maintenance_date THEN 1 ELSE 0 END) as on_time,
               SUM(CASE WHEN mh.maintenance_date > mh.next_maintenance_date THEN 1 ELSE 0 END) as late
        FROM maintenance_history mh
        WHERE mh.organization_id = ? AND mh.maintenance_date >= ?
        GROUP BY strftime('%%Y-%%m', mh.maintenance_date)
        ORDER BY month ASC
    ''', (organization_id, months_ago)).fetchall()

    conn.close()
    return jsonify([dict(d) for d in data])

@app.route('/api/maintenance/export/csv')
@login_required
def export_maintenance_csv():
    """Exportiert Wartungsdaten als CSV"""
    conn = get_db_connection()
    organization_id = session.get('organization_id')

    history = conn.execute('''
        SELECT mh.maintenance_date, mh.performed_by, mh.notes,
               mh.cost, mh.cost_parts, mh.cost_labor, mh.cost_notes,
               i.name as item_name, i.sku,
               COALESCE(mt.name, '-') as type_name,
               mh.next_maintenance_date
        FROM maintenance_history mh
        JOIN items i ON mh.item_id = i.id
        LEFT JOIN maintenance_types mt ON mh.maintenance_type_id = mt.id
        WHERE (mh.organization_id = ? OR mh.organization_id IS NULL)
        AND i.organization_id = ?
        ORDER BY mh.maintenance_date DESC
    ''', (organization_id, organization_id)).fetchall()
    conn.close()

    import csv
    import io
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['Datum', 'Artikel', 'SKU', 'Wartungstyp', 'Durchgeführt von',
                     'Notizen', 'Kosten Gesamt', 'Materialkosten', 'Arbeitskosten',
                     'Kostennotizen', 'Nächste Wartung'])

    for h in history:
        writer.writerow([
            h['maintenance_date'], h['item_name'], h['sku'] or '',
            h['type_name'], h['performed_by'] or '',
            h['notes'] or '', h['cost'] or 0, h['cost_parts'] or 0,
            h['cost_labor'] or 0, h['cost_notes'] or '',
            h['next_maintenance_date'] or ''
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=wartungsexport.csv'}
    )

@app.route('/api/maintenance/export/pdf')
@login_required
def export_maintenance_pdf():
    """Exportiert Wartungsbericht als PDF"""
    conn = get_db_connection()
    organization_id = session.get('organization_id')

    history = conn.execute('''
        SELECT mh.maintenance_date, mh.performed_by, mh.notes,
               mh.cost, mh.cost_parts, mh.cost_labor,
               i.name as item_name, i.sku,
               COALESCE(mt.name, '-') as type_name,
               mh.next_maintenance_date
        FROM maintenance_history mh
        JOIN items i ON mh.item_id = i.id
        LEFT JOIN maintenance_types mt ON mh.maintenance_type_id = mt.id
        WHERE (mh.organization_id = ? OR mh.organization_id IS NULL)
        AND i.organization_id = ?
        ORDER BY mh.maintenance_date DESC
    ''', (organization_id, organization_id)).fetchall()

    # Statistiken
    total_cost = sum((h['cost'] or 0) for h in history)
    total_parts = sum((h['cost_parts'] or 0) for h in history)
    total_labor = sum((h['cost_labor'] or 0) for h in history)

    conn.close()

    # PDF erstellen
    pdf_output = BytesIO()
    doc = SimpleDocTemplate(pdf_output, pagesize=landscape(A4),
                           rightMargin=1*cm, leftMargin=1*cm,
                           topMargin=1.5*cm, bottomMargin=1.5*cm)

    elements = []
    styles = getSampleStyleSheet()

    # Titel
    title_style = ParagraphStyle(
        'MaintTitle',
        parent=styles['Heading1'],
        fontSize=22,
        textColor=colors.HexColor('#6366f1'),
        spaceAfter=20,
        alignment=1
    )
    elements.append(Paragraph('StockMaster - Wartungsbericht', title_style))

    # Datum und Statistiken
    info_style = ParagraphStyle(
        'MaintInfo',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=8,
        alignment=1
    )
    date_str = datetime.now().strftime('%d.%m.%Y %H:%M')
    elements.append(Paragraph(f'Erstellt am: {date_str}', info_style))
    elements.append(Paragraph(
        f'Wartungen gesamt: {len(history)} | '
        f'Gesamtkosten: {total_cost:.2f} EUR | '
        f'Material: {total_parts:.2f} EUR | '
        f'Arbeit: {total_labor:.2f} EUR',
        info_style
    ))
    elements.append(Spacer(1, 0.5*cm))

    # Tabelle
    table_data = [['Datum', 'Artikel', 'SKU', 'Typ', 'Durchgef. von',
                   'Material (EUR)', 'Arbeit (EUR)', 'Gesamt (EUR)', 'Notizen']]

    for h in history:
        notes_text = (h['notes'] or '')[:40]
        if len(h['notes'] or '') > 40:
            notes_text += '...'
        table_data.append([
            h['maintenance_date'] or '-',
            (h['item_name'] or '')[:25],
            h['sku'] or '-',
            h['type_name'] or '-',
            (h['performed_by'] or '-')[:15],
            f"{(h['cost_parts'] or 0):.2f}",
            f"{(h['cost_labor'] or 0):.2f}",
            f"{(h['cost'] or 0):.2f}",
            notes_text
        ])

    col_widths = [2.2*cm, 4*cm, 2*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 5*cm]
    table = Table(table_data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6366f1')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (5, 1), (7, -1), 'RIGHT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    elements.append(table)

    doc.build(elements)
    pdf_output.seek(0)

    filename = f"Wartungsbericht_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    return send_file(
        pdf_output,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

# Dashboard Statistics API Endpoints
@app.route('/api/stats/value-trend')
@login_required
def get_value_trend():
    """Gibt die Bestandswert-Entwicklung der letzten 30 Tage zurück"""
    conn = get_db_connection()

    # Generiere Daten für die letzten 30 Tage
    days = 30
    data = []

    for i in range(days, -1, -1):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')

        # Berechne Gesamtwert für diesen Tag (vereinfacht: aktueller Bestand)
        total_value = conn.execute('''
            SELECT SUM(quantity * price) as total
            FROM items
        ''').fetchone()['total'] or 0

        data.append({
            'date': date,
            'value': round(total_value, 2)
        })

    conn.close()
    return jsonify(data)

@app.route('/api/stats/category-distribution')
@login_required
def get_category_distribution():
    """Gibt die Verteilung der Artikel pro Kategorie zurück"""
    conn = get_db_connection()

    categories = conn.execute('''
        SELECT
            COALESCE(c.name, 'Ohne Kategorie') as category,
            COUNT(i.id) as count,
            SUM(i.quantity * i.price) as value
        FROM items i
        LEFT JOIN categories c ON i.category_id = c.id
        GROUP BY i.category_id
        ORDER BY count DESC
    ''').fetchall()

    conn.close()
    return jsonify([dict(cat) for cat in categories])

@app.route('/api/stats/top-items')
@login_required
def get_top_items():
    """Gibt die Top 10 wertvollsten Artikel zurück"""
    conn = get_db_connection()

    top_items = conn.execute('''
        SELECT
            i.id,
            i.name,
            i.sku,
            i.quantity,
            i.price,
            (i.quantity * i.price) as total_value,
            c.name as category_name,
            l.name as location_name
        FROM items i
        LEFT JOIN categories c ON i.category_id = c.id
        LEFT JOIN locations l ON i.location_id = l.id
        ORDER BY total_value DESC
        LIMIT 10
    ''').fetchall()

    conn.close()
    return jsonify([dict(item) for item in top_items])

@app.route('/api/stats/recent-activity')
@login_required
def get_recent_activity():
    """Gibt die letzten Aktivitäten zurück (vereinfachte Version ohne Movement-History)"""
    conn = get_db_connection()

    # Hole die zuletzt geänderten Artikel
    recent_items = conn.execute('''
        SELECT
            i.id,
            i.name,
            i.quantity,
            c.name as category_name,
            'Aktualisiert' as action,
            datetime('now') as timestamp
        FROM items i
        LEFT JOIN categories c ON i.category_id = c.id
        ORDER BY i.id DESC
        LIMIT 10
    ''').fetchall()

    # Hole die letzten Wartungen
    recent_maintenance = conn.execute('''
        SELECT
            i.name,
            mh.maintenance_date as timestamp,
            CASE WHEN mt.name IS NOT NULL
                THEN 'Wartung: ' || mt.name
                ELSE 'Wartung durchgeführt'
            END as action,
            mh.performed_by
        FROM maintenance_history mh
        JOIN items i ON mh.item_id = i.id
        LEFT JOIN maintenance_types mt ON mh.maintenance_type_id = mt.id
        ORDER BY mh.maintenance_date DESC
        LIMIT 5
    ''').fetchall()

    conn.close()

    # Kombiniere und sortiere
    all_activities = [dict(item) for item in recent_items] + [dict(m) for m in recent_maintenance]
    all_activities.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

    return jsonify(all_activities[:10])

# Export Endpoints
@app.route('/api/export/excel')
@login_required
def export_excel():
    """Exportiert die Inventarliste als Excel-Datei"""
    conn = get_db_connection()

    # Hole alle Artikel mit Details
    items = conn.execute('''
        SELECT
            i.id,
            i.name,
            i.sku,
            i.quantity,
            i.price,
            (i.quantity * i.price) as total_value,
            c.name as category,
            l.name as location,
            i.supplier,
            i.notes,
            i.requires_maintenance,
            i.next_maintenance_date
        FROM items i
        LEFT JOIN categories c ON i.category_id = c.id
        LEFT JOIN locations l ON i.location_id = l.id
        ORDER BY i.name
    ''').fetchall()

    conn.close()

    # Erstelle Excel Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Inventar"

    # Styles
    header_fill = PatternFill(start_color="667eea", end_color="667eea", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=12)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    # Header
    headers = ['ID', 'Name', 'SKU', 'Menge', 'Preis (€)', 'Gesamtwert (€)',
               'Kategorie', 'Standort', 'Lieferant', 'Wartung', 'Nächste Wartung', 'Notizen']

    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border

    # Daten
    for row_idx, item in enumerate(items, start=2):
        ws.cell(row=row_idx, column=1, value=item['id']).border = border
        ws.cell(row=row_idx, column=2, value=item['name']).border = border
        ws.cell(row=row_idx, column=3, value=item['sku'] or '').border = border
        ws.cell(row=row_idx, column=4, value=item['quantity']).border = border

        price_cell = ws.cell(row=row_idx, column=5, value=item['price'])
        price_cell.number_format = '#,##0.00 €'
        price_cell.border = border

        total_cell = ws.cell(row=row_idx, column=6, value=item['total_value'])
        total_cell.number_format = '#,##0.00 €'
        total_cell.border = border

        ws.cell(row=row_idx, column=7, value=item['category'] or '').border = border
        ws.cell(row=row_idx, column=8, value=item['location'] or '').border = border
        ws.cell(row=row_idx, column=9, value=item['supplier'] or '').border = border
        ws.cell(row=row_idx, column=10, value='Ja' if item['requires_maintenance'] else 'Nein').border = border
        ws.cell(row=row_idx, column=11, value=item['next_maintenance_date'] or '').border = border
        ws.cell(row=row_idx, column=12, value=item['notes'] or '').border = border

    # Spaltenbreiten anpassen
    column_widths = [8, 30, 15, 10, 12, 15, 15, 15, 20, 10, 15, 40]
    for col, width in enumerate(column_widths, start=1):
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = width

    # Freeze erste Zeile
    ws.freeze_panes = 'A2'

    # Speichere in BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"Inventar_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

@app.route('/api/export/pdf')
@login_required
def export_pdf():
    """Exportiert die Inventarliste als PDF-Datei"""
    conn = get_db_connection()

    # Hole alle Artikel mit Details
    items = conn.execute('''
        SELECT
            i.name,
            i.sku,
            i.quantity,
            i.price,
            (i.quantity * i.price) as total_value,
            c.name as category,
            l.name as location
        FROM items i
        LEFT JOIN categories c ON i.category_id = c.id
        LEFT JOIN locations l ON i.location_id = l.id
        ORDER BY i.name
    ''').fetchall()

    # Berechne Statistiken
    total_items = len(items)
    total_value = sum(item['total_value'] for item in items)

    conn.close()

    # PDF erstellen
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4),
                           rightMargin=1*cm, leftMargin=1*cm,
                           topMargin=1.5*cm, bottomMargin=1.5*cm)

    elements = []
    styles = getSampleStyleSheet()

    # Titel
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#667eea'),
        spaceAfter=30,
        alignment=1  # Center
    )
    elements.append(Paragraph('StockMaster - Inventarliste', title_style))

    # Datum und Statistiken
    info_style = ParagraphStyle(
        'Info',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=20,
        alignment=1
    )
    date_str = datetime.now().strftime('%d.%m.%Y %H:%M')
    elements.append(Paragraph(f'Erstellt am: {date_str}', info_style))
    elements.append(Paragraph(f'Gesamtanzahl Artikel: {total_items} | Gesamtwert: {total_value:.2f} €', info_style))
    elements.append(Spacer(1, 0.5*cm))

    # Tabelle
    table_data = [['Name', 'SKU', 'Menge', 'Preis (€)', 'Wert (€)', 'Kategorie', 'Standort']]

    for item in items:
        table_data.append([
            item['name'][:30],  # Kürzen für PDF
            item['sku'] or '-',
            str(item['quantity']),
            f"{item['price']:.2f}",
            f"{item['total_value']:.2f}",
            item['category'] or '-',
            item['location'] or '-'
        ])

    # Tabellen-Style
    table = Table(table_data, colWidths=[6*cm, 3*cm, 2*cm, 2.5*cm, 2.5*cm, 4*cm, 4*cm])
    table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),

        # Datenzeilen
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (2, 1), (4, -1), 'RIGHT'),  # Zahlen rechtsbündig
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')])
    ]))

    elements.append(table)

    # PDF generieren
    doc.build(elements)
    output.seek(0)

    filename = f"Inventar_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    return send_file(
        output,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

@app.route('/api/items/qrcodes/print')
@login_required
def print_all_qrcodes():
    """Generiert eine Druckseite mit allen QR-Codes"""
    conn = get_db_connection()

    # Filter Parameter
    category = request.args.get('category')
    location = request.args.get('location')

    query = '''SELECT i.*, c.name as category_name, l.name as location_name
               FROM items i
               LEFT JOIN categories c ON i.category_id = c.id
               LEFT JOIN locations l ON i.location_id = l.id
               WHERE 1=1'''
    params = []

    if category:
        query += ' AND i.category_id = ?'
        params.append(category)

    if location:
        query += ' AND i.location_id = ?'
        params.append(location)

    query += ' ORDER BY i.name'

    items = conn.execute(query, params).fetchall()
    conn.close()

    # Generiere QR-Codes
    items_with_qr = []
    for item in items:
        item_dict = dict(item)
        item_dict['qrcode'] = generate_qr_code_base64(item['id'], item_dict)
        items_with_qr.append(item_dict)

    return render_template('print_qrcodes.html', items=items_with_qr)

@app.route('/api/items/barcodes/print')
@login_required
def print_all_barcodes():
    """Generiert eine Druckseite mit allen Barcodes"""
    conn = get_db_connection()
    organization_id = session.get('organization_id')

    # Filter Parameter
    item_id = request.args.get('item_id')  # Einzelner Artikel
    category = request.args.get('category')
    location = request.args.get('location')

    query = '''SELECT i.*, c.name as category_name, l.name as location_name
               FROM items i
               LEFT JOIN categories c ON i.category_id = c.id
               LEFT JOIN locations l ON i.location_id = l.id
               WHERE i.organization_id = ?'''
    params = [organization_id]

    # Einzelner Artikel
    if item_id:
        query += ' AND i.id = ?'
        params.append(item_id)
    else:
        # Filter für mehrere Artikel
        if category:
            query += ' AND i.category_id = ?'
            params.append(category)

        if location:
            query += ' AND i.location_id = ?'
            params.append(location)

    query += ' ORDER BY i.name'

    items = conn.execute(query, params).fetchall()
    conn.close()

    # Generiere Barcodes
    items_with_codes = []
    for item in items:
        item_dict = dict(item)
        item_dict['barcode'] = generate_barcode_base64(item['id'], item_dict)
        items_with_codes.append(item_dict)

    return render_template('print_barcodes.html', items=items_with_codes)

@app.route('/debug/session')
def debug_session():
    """Debug: Zeige Session-Informationen"""
    return jsonify({
        'session_keys': list(session.keys()),
        'logged_in': session.get('logged_in'),
        'user_id': session.get('user_id'),
        'username': session.get('username'),
        'organization_id': session.get('organization_id'),
        'organization_name': session.get('organization_name'),
        'is_admin': session.get('is_admin'),
        'is_org_owner': session.get('is_org_owner')
    })

def check_system_status():
    """Visuelle Systemüberprüfung beim Start mit Farben"""

    # ANSI Color Codes
    class Colors:
        HEADER = '\033[95m'
        OKBLUE = '\033[94m'
        OKCYAN = '\033[96m'
        OKGREEN = '\033[92m'
        WARNING = '\033[93m'
        FAIL = '\033[91m'
        ENDC = '\033[0m'
        BOLD = '\033[1m'
        UNDERLINE = '\033[4m'
        GRAY = '\033[90m'

    checks = []

    # ASCII Art Header (Windows-kompatibel)
    print(f"\n{Colors.OKCYAN}{Colors.BOLD}")
    print("    +===================================================================+")
    print("    |                                                                   |")
    print("    |        #####  #####  ####   ####  #    #                         |")
    print("    |       #      #    # #    # #    # #   #                          |")
    print("    |        ####  #####  #    # #      ####                           |")
    print("    |            # #    # #    # #      #  #                           |")
    print("    |       #####  #    #  ####   ####  #   #                          |")
    print("    |                                                                   |")
    print("    |                    M A S T E R                                   |")
    print("    |                  Inventory Management                            |")
    print("    +===================================================================+")
    print(f"{Colors.ENDC}")

    print(f"{Colors.BOLD}{Colors.HEADER}    {'-' * 67}{Colors.ENDC}")
    print(f"{Colors.BOLD}    {'SYSTEM CHECK':^67}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}    {'-' * 67}{Colors.ENDC}\n")

    # 1. Datenbank Check
    try:
        conn = get_db_connection()

        # Prüfe Organisationen
        org_count = conn.execute('SELECT COUNT(*) as count FROM organizations').fetchone()['count']
        db_size = os.path.getsize(DB_PATH) / 1024  # KB
        checks.append(("Database", f"{db_size:.1f} KB", "green"))
        checks.append(("Organizations", f"{org_count} registered", "green" if org_count > 0 else "yellow"))

        # Prüfe Benutzer
        user_count = conn.execute('SELECT COUNT(*) as count FROM users').fetchone()['count']
        checks.append(("Users", f"{user_count} active", "green" if user_count > 0 else "red"))

        # Prüfe Artikel
        item_count = conn.execute('SELECT COUNT(*) as count FROM items').fetchone()['count']
        checks.append(("Items", f"{item_count} in inventory", "green"))

        # Prüfe Kategorien
        cat_count = conn.execute('SELECT COUNT(*) as count FROM categories').fetchone()['count']
        checks.append(("Categories", f"{cat_count} defined", "green"))

        # Prüfe Standorte
        loc_count = conn.execute('SELECT COUNT(*) as count FROM locations').fetchone()['count']
        checks.append(("Locations", f"{loc_count} configured", "green"))

        conn.close()
    except Exception as e:
        checks.append(("Database", f"ERROR: {str(e)}", "red"))

    # 2. Templates Check
    templates_dir = 'templates'
    required_templates = ['index.html', 'login.html', 'register.html', 'profile.html']
    templates_exist = all(os.path.exists(os.path.join(templates_dir, t)) for t in required_templates)
    template_count = sum(1 for t in required_templates if os.path.exists(os.path.join(templates_dir, t)))
    checks.append(("Templates", f"{template_count}/{len(required_templates)} loaded", "green" if templates_exist else "red"))

    # 3. Static Files Check
    static_dir = 'static'
    static_exists = os.path.exists(os.path.join(static_dir, 'app.js'))
    checks.append(("JavaScript", "Loaded" if static_exists else "Missing", "green" if static_exists else "red"))

    # 4. Backup Ordner Check
    backup_exists = os.path.exists(BACKUP_FOLDER)
    checks.append(("Backup Folder", "Ready" if backup_exists else "Creating...", "green" if backup_exists else "yellow"))
    if not backup_exists:
        os.makedirs(BACKUP_FOLDER, exist_ok=True)

    # 5. Google Drive Check
    creds_exists = os.path.exists('credentials.json')
    if creds_exists:
        try:
            with open('credentials.json', 'r') as f:
                creds = json.load(f)
                is_template = 'IHRE_CLIENT_ID' in creds.get('installed', {}).get('client_id', '')
                checks.append(("Google Drive", "Template only" if is_template else "Connected", "yellow" if is_template else "green"))
        except:
            checks.append(("Google Drive", "Config error", "red"))
    else:
        checks.append(("Google Drive", "Not configured", "yellow"))

    # Ausgabe der Checks mit fancy Formatierung
    for check_name, status, color in checks:
        # Status-Symbol und Farbe basierend auf Status
        if color == "green":
            symbol = "+"
            color_code = Colors.OKGREEN
        elif color == "yellow":
            symbol = "!"
            color_code = Colors.WARNING
        else:
            symbol = "X"
            color_code = Colors.FAIL

        # Formatierte Ausgabe mit Farben
        padding = 20 - len(check_name)
        status_padding = 30 - len(status)
        print(f"    {color_code}{symbol}{Colors.ENDC} {Colors.BOLD}{check_name}{Colors.ENDC}{' ' * padding}{Colors.GRAY}|{Colors.ENDC}  {status}{' ' * status_padding}{color_code}{'o'}{Colors.ENDC}")

    print(f"\n{Colors.BOLD}{Colors.HEADER}    {'-' * 67}{Colors.ENDC}")

    # Zusammenfassung mit fancy Icons
    green_count = sum(1 for _, _, c in checks if c == "green")
    yellow_count = sum(1 for _, _, c in checks if c == "yellow")
    red_count = sum(1 for _, _, c in checks if c == "red")

    total = green_count + yellow_count + red_count
    progress = "#" * green_count + "=" * yellow_count + "-" * red_count

    print(f"\n    {Colors.BOLD}Status Overview:{Colors.ENDC}")
    print(f"    [{Colors.OKGREEN}{progress[:green_count]}{Colors.ENDC}{Colors.WARNING}{progress[green_count:green_count+yellow_count]}{Colors.ENDC}{Colors.FAIL}{progress[green_count+yellow_count:]}{Colors.ENDC}]")
    print(f"\n    {Colors.OKGREEN}+ {green_count} OK{Colors.ENDC}  {Colors.WARNING}! {yellow_count} Warnings{Colors.ENDC}  {Colors.FAIL}X {red_count} Errors{Colors.ENDC}\n")

    # Status-Nachricht
    if red_count > 0:
        print(f"    {Colors.FAIL}{Colors.BOLD}!  CRITICAL: System has errors! Please check configuration.{Colors.ENDC}\n")
    elif yellow_count > 0:
        print(f"    {Colors.WARNING}{Colors.BOLD}i  INFO: Some optional components are missing.{Colors.ENDC}\n")
    else:
        print(f"    {Colors.OKGREEN}{Colors.BOLD}+  SUCCESS: All systems operational!{Colors.ENDC}\n")

    # Server Info Box
    print(f"{Colors.BOLD}{Colors.HEADER}    {'-' * 67}{Colors.ENDC}")
    print(f"{Colors.BOLD}    {'SERVER INFORMATION':^67}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}    {'-' * 67}{Colors.ENDC}\n")

    print(f"    {Colors.OKCYAN}>>  URL:{Colors.ENDC}          {Colors.BOLD}http://localhost:5000{Colors.ENDC}")
    print(f"    {Colors.OKCYAN}>>  Network:{Colors.ENDC}      {Colors.BOLD}http://192.168.178.99:5000{Colors.ENDC}")
    print(f"\n    {Colors.OKGREEN}>>  Default Login:{Colors.ENDC}")
    print(f"    {Colors.GRAY}   Username:{Colors.ENDC}     {Colors.BOLD}admin{Colors.ENDC}")
    print(f"    {Colors.GRAY}   Password:{Colors.ENDC}     {Colors.BOLD}admin123{Colors.ENDC}")
    print(f"    {Colors.FAIL}   {Colors.BOLD}!  CHANGE PASSWORD IMMEDIATELY!{Colors.ENDC}\n")

    print(f"{Colors.BOLD}{Colors.HEADER}    {'-' * 67}{Colors.ENDC}\n")

# ============= LABEL DESIGNER =============

@app.route('/label-designer')
@login_required
def label_designer():
    """Label Designer Seite"""
    return render_template('label_designer.html')

@app.route('/label-preview')
@login_required
def label_preview():
    """Label Preview Seite"""
    return render_template('label_preview.html')

@app.route('/api/label-templates', methods=['GET', 'POST'])
@login_required
def label_templates():
    """Label Templates verwalten"""
    conn = get_db_connection()
    organization_id = session.get('organization_id')

    if request.method == 'POST':
        data = request.json

        try:
            conn.execute('''INSERT INTO label_templates
                           (organization_id, name, description, width_mm, height_mm, layout_config)
                           VALUES (?, ?, ?, ?, ?, ?)''',
                        (organization_id,
                         data['name'],
                         data.get('description', ''),
                         data['width_mm'],
                         data['height_mm'],
                         data['layout_config']))
            conn.commit()
            template_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            conn.close()

            return jsonify({'success': True, 'id': template_id, 'message': 'Template gespeichert'})
        except Exception as e:
            conn.close()
            return jsonify({'success': False, 'message': str(e)}), 500

    else:
        # GET - Liste alle Templates
        templates = conn.execute('''SELECT * FROM label_templates
                                   WHERE organization_id = ?
                                   ORDER BY created_at DESC''',
                                (organization_id,)).fetchall()
        conn.close()

        return jsonify({
            'success': True,
            'templates': [dict(t) for t in templates]
        })

@app.route('/api/label-templates/<int:id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def label_template(id):
    """Einzelnes Label Template"""
    conn = get_db_connection()
    organization_id = session.get('organization_id')

    # Prüfe ob Template existiert und zur Organisation gehört
    template = conn.execute('''SELECT * FROM label_templates
                              WHERE id = ? AND organization_id = ?''',
                           (id, organization_id)).fetchone()

    if not template:
        conn.close()
        return jsonify({'success': False, 'message': 'Template nicht gefunden'}), 404

    if request.method == 'GET':
        conn.close()
        return jsonify({'success': True, 'template': dict(template)})

    elif request.method == 'PUT':
        data = request.json

        try:
            conn.execute('''UPDATE label_templates
                           SET name = ?, description = ?, width_mm = ?, height_mm = ?,
                               layout_config = ?, updated_at = CURRENT_TIMESTAMP
                           WHERE id = ?''',
                        (data['name'],
                         data.get('description', ''),
                         data['width_mm'],
                         data['height_mm'],
                         data['layout_config'],
                         id))
            conn.commit()
            conn.close()

            return jsonify({'success': True, 'message': 'Template aktualisiert'})
        except Exception as e:
            conn.close()
            return jsonify({'success': False, 'message': str(e)}), 500

    elif request.method == 'DELETE':
        try:
            conn.execute('DELETE FROM label_templates WHERE id = ?', (id,))
            conn.commit()
            conn.close()

            return jsonify({'success': True, 'message': 'Template gelöscht'})
        except Exception as e:
            conn.close()
            return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/items/print-custom-labels')
@login_required
def print_custom_labels():
    """Drucke Etiketten mit Custom Template"""
    conn = get_db_connection()
    organization_id = session.get('organization_id')

    # Template ID aus Query Parameter
    template_id = request.args.get('template_id')

    if not template_id:
        return jsonify({'success': False, 'message': 'Template ID fehlt'}), 400

    # Hole Template
    template = conn.execute('''SELECT * FROM label_templates
                              WHERE id = ? AND organization_id = ?''',
                           (template_id, organization_id)).fetchone()

    if not template:
        conn.close()
        return jsonify({'success': False, 'message': 'Template nicht gefunden'}), 404

    # Filter Parameter
    category = request.args.get('category')
    location = request.args.get('location')
    item_id = request.args.get('item_id')

    query = '''SELECT i.*, c.name as category_name, l.name as location_name
               FROM items i
               LEFT JOIN categories c ON i.category_id = c.id
               LEFT JOIN locations l ON i.location_id = l.id
               WHERE i.organization_id = ?'''
    params = [organization_id]

    if item_id:
        query += ' AND i.id = ?'
        params.append(item_id)
    elif category:
        query += ' AND i.category_id = ?'
        params.append(category)
    elif location:
        query += ' AND i.location_id = ?'
        params.append(location)

    query += ' ORDER BY i.name'

    items = conn.execute(query, params).fetchall()
    conn.close()

    # Generiere Barcodes und QR-Codes für alle Items
    items_with_codes = []
    for item in items:
        item_dict = dict(item)
        item_dict['barcode'] = generate_barcode_base64(item['id'], item_dict)
        item_dict['qrcode'] = generate_qr_code_base64(item['id'], item_dict)
        items_with_codes.append(item_dict)

    return render_template('print_custom_labels.html',
                          items=items_with_codes,
                          template=dict(template))

@app.route('/debug-session')
def debug_session_page():
    """Debug-Seite für Session-Probleme"""
    return render_template('debug_session.html',
                          secret_key_set=app.config.get('SECRET_KEY') is not None,
                          config=app.config,
                          session_data=dict(session),
                          logged_in='logged_in' in session,
                          cookies=dict(request.cookies))

@app.route('/debug-login', methods=['POST'])
def debug_login():
    """Test-Login für Debugging"""
    username = request.form.get('username')
    password = request.form.get('password')

    user = verify_user(username, password)

    if user:
        session.clear()
        session['logged_in'] = True
        session['user_id'] = user['id']
        session['username'] = username
        session['organization_id'] = user['organization_id']
        session['organization_name'] = user['organization_name']
        session['is_admin'] = user['is_admin']
        session['is_org_owner'] = user['is_org_owner']
        session.modified = True

        return redirect(url_for('debug_session_page'))
    else:
        return redirect(url_for('debug_session_page'))

# Ensure schema/migrations are applied in WSGI deployments too.
# In production, app is often imported (not run via __main__), so this
# must execute at import time to avoid SQL errors on newer routes.
init_db()

if __name__ == '__main__':
    # Systemcheck durchführen
    check_system_status()

    # Google Drive initialisieren
    init_google_drive()

    # Auto-Backup-Service starten (falls aktiviert)
    try:
        from auto_backup import get_backup_service

        # Konfiguration aus Umgebungsvariablen oder Defaults
        auto_backup_enabled = os.getenv('AUTO_BACKUP_ENABLED', 'true').lower() == 'true'
        backup_interval_hours = int(os.getenv('BACKUP_INTERVAL_HOURS', '24'))
        keep_backups = int(os.getenv('KEEP_BACKUPS', '30'))

        if auto_backup_enabled:
            backup_service = get_backup_service(
                db_path=DB_PATH,
                backup_interval_hours=backup_interval_hours,
                keep_backups=keep_backups
            )
            backup_service.start()
            print(f"✓ Automatisches Backup aktiviert (Intervall: {backup_interval_hours}h, behalte: {keep_backups} Backups)")
        else:
            print("ℹ Auto-Backup deaktiviert (AUTO_BACKUP_ENABLED=false)")
    except Exception as e:
        print(f"⚠️  Auto-Backup konnte nicht gestartet werden: {e}")
        print("   Die App läuft weiter ohne automatische Backups")

    # E-Mail-Benachrichtigungs-Service starten (falls aktiviert)
    try:
        from notification_service import get_notification_service

        notifications_enabled = os.getenv('NOTIFICATIONS_ENABLED', 'false').lower() == 'true'
        notification_email = os.getenv('NOTIFICATION_EMAIL')  # Fallback-Adresse
        notification_interval_hours = int(os.getenv('NOTIFICATION_CHECK_INTERVAL_HOURS', '24'))

        if notifications_enabled:
            notification_service = get_notification_service(
                db_path=DB_PATH,
                check_interval_hours=notification_interval_hours,
                notification_email=notification_email
            )
            notification_service.start()
            print(f"✓ E-Mail-Benachrichtigungen aktiviert (Intervall: {notification_interval_hours}h)")
            print("  Benachrichtigungen werden an Benutzer mit hinterlegter E-Mail gesendet")
            if notification_email:
                print(f"  Fallback-E-Mail: {notification_email}")
        else:
            print("ℹ E-Mail-Benachrichtigungen deaktiviert (NOTIFICATIONS_ENABLED=false)")
    except Exception as e:
        print(f"⚠️  E-Mail-Benachrichtigungen konnten nicht gestartet werden: {e}")
        print("   Die App läuft weiter ohne E-Mail-Benachrichtigungen")

    # HTTPS-Konfiguration für Kamera-Zugriff (getUserMedia API)
    # Die Kamera-API funktioniert nur über HTTPS oder localhost
    ssl_context = None
    https_enabled = os.path.exists('cert.pem') and os.path.exists('key.pem')

    if https_enabled:
        ssl_context = ('cert.pem', 'key.pem')

        # Lokale IPs für die Ausgabe ermitteln
        local_ips = []
        try:
            import subprocess
            result = subprocess.run(['ipconfig'], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if 'IPv4' in line and ':' in line:
                    ip = line.split(':')[1].strip()
                    if ip and ip != '127.0.0.1':
                        local_ips.append(ip)
        except:
            pass

        print("\n" + "="*60)
        print("OK HTTPS aktiviert - Kamera-Zugriff verfuegbar")
        print("="*60)
        print("\nZugriff ueber:")
        print(f"  - https://localhost:5000 (auf diesem PC)")
        for ip in local_ips:
            print(f"  - https://{ip}:5000 (von anderen Geraeten)")

        print("\n! WICHTIG: Selbst-signiertes Zertifikat")
        print("   Ihr Browser zeigt eine Sicherheitswarnung - das ist normal!")
        print("   -> Klicken Sie auf 'Erweitert' und 'Trotzdem fortfahren'")
        print("   -> Auf dem Handy: 'thisisunsafe' eintippen falls noetig")
        print("="*60 + "\n")
    else:
        print("\n" + "="*60)
        print("! HTTPS nicht aktiviert")
        print("="*60)
        print("\nKeine SSL-Zertifikate gefunden (cert.pem, key.pem)")
        print("\n! Kamera-Zugriff funktioniert nur:")
        print("   - Ueber HTTPS (empfohlen fuer Handy-Zugriff)")
        print("   - ODER ueber http://localhost:5000 (nur auf diesem PC)")
        print("\nZertifikate erstellen:")
        print("   python generate_cert.py")
        print("="*60 + "\n")

    app.run(debug=True, host='0.0.0.0', port=5000, ssl_context=ssl_context)

  
