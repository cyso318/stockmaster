#!/usr/bin/env python3
"""
Migration Script: Fügt invitation_tokens Tabelle hinzu
"""

import sqlite3

DB_PATH = 'inventory.db'

def migrate():
    print("Starte Migration: invitation_tokens Tabelle hinzufügen...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Prüfe ob Tabelle bereits existiert
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='invitation_tokens'")
    if cursor.fetchone():
        print("OK: Tabelle invitation_tokens existiert bereits")
        conn.close()
        return

    # Erstelle invitation_tokens Tabelle
    cursor.execute('''CREATE TABLE IF NOT EXISTS invitation_tokens
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

    conn.commit()

    # Verifiziere
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='invitation_tokens'")
    if cursor.fetchone():
        print("OK: Tabelle invitation_tokens erfolgreich erstellt")
    else:
        print("ERROR: Fehler beim Erstellen der Tabelle")

    conn.close()
    print("Migration abgeschlossen!")

if __name__ == '__main__':
    migrate()
