-- ============================================================
-- StockMaster — Supabase PostgreSQL Schema
-- Dieses SQL im Supabase SQL-Editor ausführen
-- ============================================================

-- Organisationen
CREATE TABLE IF NOT EXISTS organizations (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL UNIQUE,
    email       TEXT DEFAULT '',
    phone       TEXT DEFAULT '',
    plan        TEXT DEFAULT 'free',
    max_users   INTEGER DEFAULT 5,
    max_items   INTEGER DEFAULT 1000,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Benutzer (verknüpft mit Supabase Auth via auth_id)
CREATE TABLE IF NOT EXISTS users (
    id              BIGSERIAL PRIMARY KEY,
    auth_id         UUID UNIQUE,          -- Supabase Auth user id
    organization_id BIGINT REFERENCES organizations(id),
    username        TEXT NOT NULL,
    email           TEXT,
    first_name      TEXT DEFAULT '',
    last_name       TEXT DEFAULT '',
    is_admin        BOOLEAN DEFAULT FALSE,
    is_org_owner    BOOLEAN DEFAULT FALSE,
    notify_low_stock    BOOLEAN DEFAULT TRUE,
    notify_maintenance  BOOLEAN DEFAULT TRUE,
    last_login      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Einladungstokens
CREATE TABLE IF NOT EXISTS invitation_tokens (
    id              BIGSERIAL PRIMARY KEY,
    organization_id BIGINT REFERENCES organizations(id),
    token           TEXT NOT NULL UNIQUE,
    created_by      BIGINT REFERENCES users(id),
    expires_at      TIMESTAMPTZ,
    is_used         BOOLEAN DEFAULT FALSE,
    used_by         BIGINT REFERENCES users(id),
    used_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Kategorien
CREATE TABLE IF NOT EXISTS categories (
    id              BIGSERIAL PRIMARY KEY,
    organization_id BIGINT REFERENCES organizations(id),
    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organization_id, name)
);

-- Standorte
CREATE TABLE IF NOT EXISTS locations (
    id              BIGSERIAL PRIMARY KEY,
    organization_id BIGINT REFERENCES organizations(id),
    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organization_id, name)
);

-- Artikel
CREATE TABLE IF NOT EXISTS items (
    id                          BIGSERIAL PRIMARY KEY,
    organization_id             BIGINT REFERENCES organizations(id),
    sku                         TEXT,
    name                        TEXT NOT NULL,
    barcode                     TEXT,
    description                 TEXT,
    category_id                 BIGINT REFERENCES categories(id),
    location_id                 BIGINT REFERENCES locations(id),
    quantity                    INTEGER DEFAULT 0,
    min_quantity                INTEGER DEFAULT 0,
    unit                        TEXT DEFAULT 'Stück',
    price                       NUMERIC(12,2) DEFAULT 0,
    supplier                    TEXT,
    notes                       TEXT,
    requires_maintenance        BOOLEAN DEFAULT FALSE,
    maintenance_interval_days   INTEGER,
    last_maintenance_date       DATE,
    next_maintenance_date       DATE,
    maintenance_notes           TEXT,
    image_path                  TEXT,
    is_group                    BOOLEAN DEFAULT FALSE,
    group_id                    BIGINT REFERENCES items(id),
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organization_id, sku)
);

-- Bewegungen (Ein-/Ausbuchungen)
CREATE TABLE IF NOT EXISTS movements (
    id          BIGSERIAL PRIMARY KEY,
    item_id     BIGINT REFERENCES items(id),
    user_id     BIGINT REFERENCES users(id),
    type        TEXT NOT NULL,   -- 'in' oder 'out'
    quantity    INTEGER NOT NULL,
    reference   TEXT,
    notes       TEXT,
    slip_id     BIGINT,          -- FK zu withdrawal_slips (nach Tabellenerstellung)
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Entnahmescheine
CREATE TABLE IF NOT EXISTS withdrawal_slips (
    id              BIGSERIAL PRIMARY KEY,
    organization_id BIGINT REFERENCES organizations(id),
    user_id         BIGINT REFERENCES users(id),
    reference       TEXT,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- FK nachträglich hinzufügen
ALTER TABLE movements
    ADD CONSTRAINT fk_movements_slip
    FOREIGN KEY (slip_id) REFERENCES withdrawal_slips(id)
    NOT VALID;

-- Label Templates
CREATE TABLE IF NOT EXISTS label_templates (
    id              BIGSERIAL PRIMARY KEY,
    organization_id BIGINT REFERENCES organizations(id),
    name            TEXT NOT NULL,
    description     TEXT,
    width_mm        NUMERIC DEFAULT 62,
    height_mm       NUMERIC DEFAULT 42,
    layout_config   TEXT NOT NULL,
    is_default      BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Wartungstypen
CREATE TABLE IF NOT EXISTS maintenance_types (
    id                      BIGSERIAL PRIMARY KEY,
    organization_id         BIGINT REFERENCES organizations(id),
    name                    TEXT NOT NULL,
    description             TEXT,
    color                   TEXT DEFAULT '#7c3aed',
    icon                    TEXT DEFAULT 'wrench',
    default_interval_days   INTEGER,
    is_active               BOOLEAN DEFAULT TRUE,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organization_id, name)
);

-- Wartungspläne pro Artikel
CREATE TABLE IF NOT EXISTS item_maintenance_schedules (
    id                      BIGSERIAL PRIMARY KEY,
    item_id                 BIGINT REFERENCES items(id) ON DELETE CASCADE,
    maintenance_type_id     BIGINT REFERENCES maintenance_types(id),
    interval_days           INTEGER NOT NULL,
    last_date               DATE,
    next_date               DATE,
    assigned_user_id        BIGINT REFERENCES users(id),
    is_active               BOOLEAN DEFAULT TRUE,
    priority                TEXT DEFAULT 'normal',
    notes                   TEXT,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(item_id, maintenance_type_id)
);

-- Wartungshistorie
CREATE TABLE IF NOT EXISTS maintenance_history (
    id                      BIGSERIAL PRIMARY KEY,
    item_id                 BIGINT REFERENCES items(id),
    user_id                 BIGINT REFERENCES users(id),
    organization_id         BIGINT REFERENCES organizations(id),
    maintenance_type_id     BIGINT REFERENCES maintenance_types(id),
    schedule_id             BIGINT REFERENCES item_maintenance_schedules(id),
    maintenance_date        DATE NOT NULL,
    performed_by            TEXT,
    notes                   TEXT,
    next_maintenance_date   DATE,
    cost                    NUMERIC(10,2) DEFAULT 0,
    cost_parts              NUMERIC(10,2) DEFAULT 0,
    cost_labor              NUMERIC(10,2) DEFAULT 0,
    cost_notes              TEXT,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- Wartungs-Checklisten
CREATE TABLE IF NOT EXISTS maintenance_checklists (
    id                  BIGSERIAL PRIMARY KEY,
    maintenance_type_id BIGINT REFERENCES maintenance_types(id) ON DELETE CASCADE,
    organization_id     BIGINT REFERENCES organizations(id),
    name                TEXT NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Checklisten-Prüfpunkte
CREATE TABLE IF NOT EXISTS checklist_items (
    id              BIGSERIAL PRIMARY KEY,
    checklist_id    BIGINT REFERENCES maintenance_checklists(id) ON DELETE CASCADE,
    description     TEXT NOT NULL,
    sort_order      INTEGER DEFAULT 0,
    is_required     BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Checklisten-Ergebnisse
CREATE TABLE IF NOT EXISTS maintenance_checklist_results (
    id                      BIGSERIAL PRIMARY KEY,
    maintenance_history_id  BIGINT REFERENCES maintenance_history(id) ON DELETE CASCADE,
    checklist_item_id       BIGINT REFERENCES checklist_items(id),
    is_checked              BOOLEAN DEFAULT FALSE,
    notes                   TEXT
);

-- ============================================================
-- Row Level Security deaktivieren (App nutzt Service Role Key)
-- ============================================================
ALTER TABLE organizations                   DISABLE ROW LEVEL SECURITY;
ALTER TABLE users                           DISABLE ROW LEVEL SECURITY;
ALTER TABLE invitation_tokens               DISABLE ROW LEVEL SECURITY;
ALTER TABLE categories                      DISABLE ROW LEVEL SECURITY;
ALTER TABLE locations                       DISABLE ROW LEVEL SECURITY;
ALTER TABLE items                           DISABLE ROW LEVEL SECURITY;
ALTER TABLE movements                       DISABLE ROW LEVEL SECURITY;
ALTER TABLE withdrawal_slips                DISABLE ROW LEVEL SECURITY;
ALTER TABLE label_templates                 DISABLE ROW LEVEL SECURITY;
ALTER TABLE maintenance_types               DISABLE ROW LEVEL SECURITY;
ALTER TABLE item_maintenance_schedules      DISABLE ROW LEVEL SECURITY;
ALTER TABLE maintenance_history             DISABLE ROW LEVEL SECURITY;
ALTER TABLE maintenance_checklists          DISABLE ROW LEVEL SECURITY;
ALTER TABLE checklist_items                 DISABLE ROW LEVEL SECURITY;
ALTER TABLE maintenance_checklist_results   DISABLE ROW LEVEL SECURITY;
