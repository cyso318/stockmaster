# StockMaster — CLAUDE.md

## Project Overview

StockMaster is a web-based inventory management system with Google Drive backup synchronization. It is a German-language application built for small to medium organizations to manage warehouse stock, generate QR/barcodes, and track item movements.

**Tech Stack:**
- Backend: Python 3.8+, Flask 3.0.0
- Database: SQLite (`inventory.db`)
- Frontend: HTML5, Jinja2 templates, vanilla JavaScript
- Auth: bcrypt + session-based
- Cloud: Google Drive API (OAuth 2.0)
- Security: Flask-Talisman, Flask-WTF (CSRF), Flask-Limiter

---

## Running the Project

```bash
# Activate virtual environment
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env — especially SECRET_KEY

# Start app (auto-creates DB on first run)
python app.py
# Or use convenience scripts:
./start.sh      # Linux/Mac
start.bat       # Windows
```

App runs at **http://localhost:5000**

### Production (Gunicorn)
```bash
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

---

## Project Structure

```
stockmaster/
├── app.py                    # Main Flask app (~4200 lines) — all routes and logic
├── gdrive_sync.py            # Google Drive sync module
├── auto_backup.py            # Automatic backup service (threaded)
├── notification_service.py   # Email notifications for low stock
├── email_service.py          # SMTP handler
├── static/
│   ├── app.js                # Main client-side logic
│   ├── label_designer.js     # Custom label designer
│   ├── quagga-scanner.js     # Client-side barcode scanner
│   ├── backup_manager.js     # Backup management UI
│   ├── sw.js                 # Service Worker (PWA)
│   └── manifest.json         # PWA manifest
├── templates/                # 16 Jinja2 HTML templates
├── backups/                  # Local backup directory
├── inventory.db              # SQLite database (auto-created)
├── credentials.json          # Google OAuth credentials (user-provided)
└── token.pickle              # Google auth token (auto-generated)
```

---

## Key Configuration

| File | Purpose |
|------|---------|
| `.env` | App secrets and feature flags (copy from `.env.example`) |
| `credentials.json` | Google OAuth 2.0 credentials (required for Drive sync) |
| `token.pickle` | Google auth token — auto-generated on first OAuth flow |
| `inventory.db` | SQLite database — created automatically on first run |

### Important `.env` variables
```
SECRET_KEY=<random-key>
DATABASE_PATH=inventory.db
AUTO_BACKUP_ENABLED=true
BACKUP_INTERVAL_HOURS=24
NOTIFICATIONS_ENABLED=false
HOST=0.0.0.0
PORT=5000
DEBUG=False
```

---

## Database Schema

All tables are created by `init_db()` in `app.py` on startup. Key tables:

- **users** — accounts with bcrypt password hashes
- **organizations** — multi-tenant support (most tables have `org_id`)
- **items** — inventory items (SKU, category, location, price, min stock)
- **categories** / **locations** — classification/storage
- **movements** — stock in/out audit trail
- **label_templates** — custom label designer templates
- **sync_log** — Google Drive sync history
- **invitation_tokens** — user registration via invite links

---

## Key Features

- Inventory CRUD with SKU, pricing, min-stock thresholds
- Stock movements with full audit trail
- QR code and barcode generation and printing
- Custom label designer (saved templates)
- Google Drive automatic daily backups
- CSV/Excel export
- Multi-user with admin roles
- PWA with offline support (Service Worker)
- Client-side barcode scanning (Quagga)
- Email alerts for low stock (optional)

---

## Security

Security is a primary concern in this project:

- Passwords hashed with bcrypt
- CSRF protection via Flask-WTF on all forms
- Rate limiting on login (5/min) and API (100/min) via Flask-Limiter
- Security headers via Flask-Talisman
- Session timeout (30 minutes), secure cookies
- Brute-force login protection

Do not weaken these protections without explicit reason.

---

## Testing

There is **no automated test suite**. Testing is done manually via the web UI.

- Database schema validation runs automatically on startup via `init_db()`
- API endpoints can be tested with curl or Postman
- For new routes, test manually with various roles (admin vs. regular user)

---

## Google Drive Setup (Optional)

1. Create OAuth 2.0 credentials in Google Cloud Console
2. Download as `credentials.json` to the project root
3. First run opens a browser auth flow — generates `token.pickle`
4. Or trigger sync in-app: "Sync zu Google Drive" button

---

## Development Notes

- **Language:** UI, templates, and user-facing text are in **German**
- **Multi-tenancy:** Users belong to organizations (`org_id`); always scope DB queries by org
- **app.py is large:** All Flask routes are in a single file (~4200 lines) — search by route path or function name
- **Frontend:** No bundler/build step — vanilla JS served directly from `static/`
- **No migrations:** Schema changes require updating `init_db()` and handling existing DBs manually

---

## Docs

| File | Content |
|------|---------|
| `README.md` | Full installation and usage guide (German) |
| `QUICKSTART.md` | 5-minute quick start |
| `DEPLOYMENT_GUIDE.md` | Production deployment |
| `SECURITY.md` | Security feature overview |
| `AUTO_BACKUP_GUIDE.md` | Google Drive backup setup |
| `INSTALL_WINDOWS.md` | Windows-specific installation |
| `LABEL_TEMPLATES_FIX.md` | Custom label template configuration |
