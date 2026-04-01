# StockMaster — CLAUDE.md

## Project Overview

StockMaster is a web-based inventory management system. German-language app for small to medium organizations — inventory tracking, QR/barcodes, stock movements, maintenance scheduling.

**Tech Stack:**
- Backend: Python 3.8+, Flask 3.0.0
- Database: Supabase (PostgreSQL) via supabase-py v2
- Frontend: HTML5, Jinja2 templates, vanilla JavaScript
- Auth: Supabase Auth (email + password)
- Security: Flask-Talisman, Flask-WTF (CSRF), Flask-Limiter

---

## Running the Project

```bash
# Activate virtual environment
venv\Scripts\activate           # Windows
source venv/bin/activate        # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
# Edit .env — set SECRET_KEY, SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY

# Start app
python app.py
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
├── app.py                    # Main Flask app (~1000 lines) — all routes and logic
├── schema.sql                # Supabase PostgreSQL schema (run once in Supabase SQL editor)
├── .env                      # Secrets: SECRET_KEY, SUPABASE_* keys
├── static/
│   ├── app.js                # Main client-side logic
│   ├── label_designer.js     # Custom label designer
│   ├── quagga-scanner.js     # Client-side barcode scanner
│   ├── sw.js                 # Service Worker (PWA)
│   └── manifest.json         # PWA manifest
├── templates/                # Jinja2 HTML templates
└── static/uploads/items/     # Item images (local disk)
```

---

## Key Configuration (.env)

```
SECRET_KEY=<random-key-32-chars>
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_ANON_KEY=sb_publishable_...
SUPABASE_SERVICE_KEY=sb_secret_...
SESSION_TIMEOUT_MINUTES=30
HOST=0.0.0.0
PORT=5000
DEBUG=False
```

---

## Supabase Setup

1. Run `schema.sql` in the Supabase SQL editor (creates all 15 tables)
2. All tables have RLS disabled — app uses service role key
3. Supabase Auth handles passwords (email + password login)
4. `users` table has `auth_id UUID` linking to `auth.users`

Two clients in app.py:
- `sb = create_client(URL, SERVICE_KEY)` — all DB operations + admin auth
- `sb_auth = create_client(URL, ANON_KEY)` — user sign-in

---

## Database Schema

Key tables (defined in `schema.sql`):

- **users** — `auth_id` links to Supabase Auth; `organization_id`, `is_admin`, `is_org_owner`
- **organizations** — multi-tenant; every table scoped by `organization_id`
- **items** — SKU, barcode, category, location, quantity, min_quantity, price, maintenance fields
- **categories** / **locations** — org-scoped classification
- **movements** — stock in/out audit trail with `slip_id` FK
- **withdrawal_slips** — Entnahmescheine (single + batch)
- **maintenance_types** / **item_maintenance_schedules** / **maintenance_history** — maintenance tracking
- **label_templates** — custom label designer templates
- **invitation_tokens** — user registration via invite codes

---

## Supabase Query Patterns

```python
# SELECT with JOIN (FK embedding)
sb.table('items').select('*, categories(name), locations(name)').eq('organization_id', org_id).execute().data

# INSERT returning id
row = sb.table('items').insert({...}).execute().data[0]
id = row['id']

# UPDATE
sb.table('items').update({'quantity': new_qty}).eq('id', id).execute()

# DELETE
sb.table('items').delete().eq('id', id).execute()

# COUNT
count = sb.table('items').select('id', count='exact').eq('organization_id', org_id).execute().count

# Auth: sign in
sb_auth.auth.sign_in_with_password({"email": email, "password": password})

# Auth: create user (admin)
sb.auth.admin.create_user({"email": email, "password": pw, "email_confirm": True})

# Auth: change password
sb.auth.admin.update_user_by_id(auth_id, {"password": new_password})
```

Normalize embedded FK responses with `_normalize_item()` helper in app.py.

---

## Key Features

- Inventory CRUD with SKU, pricing, min-stock thresholds, item groups
- Stock movements (in/out) with full audit trail
- Entnahmescheine (withdrawal slips) — single + Sammelschein (batch)
- QR code and barcode generation and printing
- Custom label designer (saved templates)
- CSV/Excel/PDF export
- Multi-user with admin roles + invitation tokens
- Maintenance scheduling with types, checklists, cost tracking
- PWA with offline support (Service Worker)
- Client-side barcode scanning (Quagga)

---

## Security

- Supabase Auth handles password hashing and verification
- CSRF protection via Flask-WTF on all mutation endpoints
- Rate limiting on login (5/min) and API (100/min) via Flask-Limiter
- Security headers via Flask-Talisman
- Session timeout (30 minutes), brute-force lockout (15 min after 5 failures)
- All DB queries scoped by `organization_id` from session

Do not weaken these protections without explicit reason.

---

## Development Notes

- **Language:** UI, templates, and user-facing text are in **German**
- **Multi-tenancy:** Always scope queries by `org_id = session.get('organization_id')`
- **No migrations:** Schema changes require updating `schema.sql` and re-running in Supabase
- **Frontend:** No bundler/build step — vanilla JS from `static/`
- **Testing:** No automated test suite — test manually via web UI

---

## Docs

| File | Content |
|------|---------|
| `README.md` | Full installation and usage guide (German) |
| `schema.sql` | Supabase PostgreSQL schema |
