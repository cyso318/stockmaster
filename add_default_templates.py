"""
Script zum Hinzufügen von Standard Label-Templates
"""
import sqlite3
import json
from datetime import datetime

# Standard-Templates
templates = [
    {
        'name': 'Brother QL-700 Standard (62x29mm)',
        'description': 'Standard-Layout für Brother QL-700 Etikettendrucker',
        'width_mm': 62,
        'height_mm': 29,
        'layout_config': json.dumps({
            'width': 62,
            'height': 29,
            'elements': [
                {
                    'type': 'text',
                    'field': 'name',
                    'x': 5,
                    'y': 5,
                    'width': 35,
                    'height': 8,
                    'fontSize': 10,
                    'fontWeight': 'bold'
                },
                {
                    'type': 'barcode',
                    'x': 42,
                    'y': 4,
                    'width': 18,
                    'height': 20
                },
                {
                    'type': 'text',
                    'field': 'sku',
                    'x': 5,
                    'y': 15,
                    'width': 30,
                    'height': 6,
                    'fontSize': 8
                },
                {
                    'type': 'text',
                    'field': 'location',
                    'x': 5,
                    'y': 22,
                    'width': 30,
                    'height': 5,
                    'fontSize': 7
                }
            ]
        })
    },
    {
        'name': 'Klein & Kompakt (40x20mm)',
        'description': 'Kleines Etikett mit Barcode und Name',
        'width_mm': 40,
        'height_mm': 20,
        'layout_config': json.dumps({
            'width': 40,
            'height': 20,
            'elements': [
                {
                    'type': 'text',
                    'field': 'name',
                    'x': 2,
                    'y': 2,
                    'width': 36,
                    'height': 6,
                    'fontSize': 8,
                    'fontWeight': 'bold'
                },
                {
                    'type': 'barcode',
                    'x': 10,
                    'y': 9,
                    'width': 20,
                    'height': 10
                }
            ]
        })
    },
    {
        'name': 'Groß mit Bild (62x42mm)',
        'description': 'Großes Etikett mit Artikelbild, Name und Barcode',
        'width_mm': 62,
        'height_mm': 42,
        'layout_config': json.dumps({
            'width': 62,
            'height': 42,
            'elements': [
                {
                    'type': 'text',
                    'field': 'name',
                    'x': 20,
                    'y': 3,
                    'width': 40,
                    'height': 8,
                    'fontSize': 10,
                    'fontWeight': 'bold'
                },
                {
                    'type': 'image',
                    'x': 2,
                    'y': 3,
                    'width': 15,
                    'height': 15
                },
                {
                    'type': 'barcode',
                    'x': 20,
                    'y': 13,
                    'width': 38,
                    'height': 18
                },
                {
                    'type': 'text',
                    'field': 'sku',
                    'x': 2,
                    'y': 20,
                    'width': 15,
                    'height': 6,
                    'fontSize': 7
                },
                {
                    'type': 'text',
                    'field': 'location',
                    'x': 2,
                    'y': 27,
                    'width': 15,
                    'height': 5,
                    'fontSize': 6
                },
                {
                    'type': 'text',
                    'field': 'category',
                    'x': 2,
                    'y': 34,
                    'width': 15,
                    'height': 5,
                    'fontSize': 6
                }
            ]
        })
    },
    {
        'name': 'QR-Code Variante (50x50mm)',
        'description': 'Quadratisches Etikett mit QR-Code statt Barcode',
        'width_mm': 50,
        'height_mm': 50,
        'layout_config': json.dumps({
            'width': 50,
            'height': 50,
            'elements': [
                {
                    'type': 'text',
                    'field': 'name',
                    'x': 3,
                    'y': 3,
                    'width': 44,
                    'height': 8,
                    'fontSize': 10,
                    'fontWeight': 'bold'
                },
                {
                    'type': 'qrcode',
                    'x': 15,
                    'y': 13,
                    'width': 20,
                    'height': 20
                },
                {
                    'type': 'text',
                    'field': 'sku',
                    'x': 3,
                    'y': 35,
                    'width': 44,
                    'height': 6,
                    'fontSize': 8
                },
                {
                    'type': 'text',
                    'field': 'location',
                    'x': 3,
                    'y': 42,
                    'width': 44,
                    'height': 5,
                    'fontSize': 7
                }
            ]
        })
    }
]

def add_templates():
    """Fügt Standard-Templates für alle Organisationen hinzu"""
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()

    # Hole alle Organisationen
    organizations = cursor.execute('SELECT id, name FROM organizations').fetchall()

    if not organizations:
        print("❌ Keine Organisationen gefunden!")
        conn.close()
        return

    print(f"📋 Gefunden: {len(organizations)} Organisation(en)")

    added_count = 0

    for org_id, org_name in organizations:
        print(f"\n🏢 Organisation: {org_name} (ID: {org_id})")

        # Prüfe ob bereits Templates vorhanden sind
        existing = cursor.execute(
            'SELECT COUNT(*) FROM label_templates WHERE organization_id = ?',
            (org_id,)
        ).fetchone()[0]

        if existing > 0:
            print(f"   ℹ️  Bereits {existing} Template(s) vorhanden - überspringe")
            continue

        # Füge Templates hinzu
        for template in templates:
            try:
                cursor.execute('''
                    INSERT INTO label_templates
                    (organization_id, name, description, width_mm, height_mm, layout_config, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    org_id,
                    template['name'],
                    template['description'],
                    template['width_mm'],
                    template['height_mm'],
                    template['layout_config'],
                    datetime.now().isoformat()
                ))
                print(f"   ✅ {template['name']}")
                added_count += 1
            except Exception as e:
                print(f"   ❌ Fehler bei {template['name']}: {e}")

    conn.commit()
    conn.close()

    print(f"\n🎉 Fertig! {added_count} Template(s) hinzugefügt")

if __name__ == '__main__':
    print("=" * 60)
    print("  Standard Label-Templates hinzufügen")
    print("=" * 60)
    add_templates()
