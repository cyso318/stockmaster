#!/bin/bash
# Script zum Hinzufügen von Standard Label-Templates auf dem Server

echo "======================================"
echo "  Label-Templates hinzufügen"
echo "======================================"

cd ~/stockmaster

# Template 1: Brother QL-700 Standard
python3 << 'EOF'
import sqlite3, json

conn = sqlite3.connect('inventory.db')
orgs = conn.execute('SELECT id, name FROM organizations').fetchall()

template1 = {
    'name': 'Brother QL-700 Standard (62x29mm)',
    'description': 'Standard-Layout für Brother QL-700',
    'width_mm': 62,
    'height_mm': 29,
    'layout': json.dumps({
        'width': 62,
        'height': 29,
        'elements': [
            {'type': 'text', 'field': 'name', 'x': 5, 'y': 5, 'width': 35, 'height': 8, 'fontSize': 10, 'fontWeight': 'bold'},
            {'type': 'barcode', 'x': 42, 'y': 4, 'width': 18, 'height': 20},
            {'type': 'text', 'field': 'sku', 'x': 5, 'y': 15, 'width': 30, 'height': 6, 'fontSize': 8},
            {'type': 'text', 'field': 'location', 'x': 5, 'y': 22, 'width': 30, 'height': 5, 'fontSize': 7}
        ]
    })
}

template2 = {
    'name': 'Klein & Kompakt (40x20mm)',
    'description': 'Kleines Etikett mit Barcode',
    'width_mm': 40,
    'height_mm': 20,
    'layout': json.dumps({
        'width': 40,
        'height': 20,
        'elements': [
            {'type': 'text', 'field': 'name', 'x': 2, 'y': 2, 'width': 36, 'height': 6, 'fontSize': 8, 'fontWeight': 'bold'},
            {'type': 'barcode', 'x': 10, 'y': 9, 'width': 20, 'height': 10}
        ]
    })
}

template3 = {
    'name': 'Groß mit Bild (62x42mm)',
    'description': 'Mit Artikelbild, Name und Barcode',
    'width_mm': 62,
    'height_mm': 42,
    'layout': json.dumps({
        'width': 62,
        'height': 42,
        'elements': [
            {'type': 'text', 'field': 'name', 'x': 20, 'y': 3, 'width': 40, 'height': 8, 'fontSize': 10, 'fontWeight': 'bold'},
            {'type': 'image', 'x': 2, 'y': 3, 'width': 15, 'height': 15},
            {'type': 'barcode', 'x': 20, 'y': 13, 'width': 38, 'height': 18},
            {'type': 'text', 'field': 'sku', 'x': 2, 'y': 20, 'width': 15, 'height': 6, 'fontSize': 7}
        ]
    })
}

template4 = {
    'name': 'QR-Code Variante (50x50mm)',
    'description': 'Quadratisch mit QR-Code',
    'width_mm': 50,
    'height_mm': 50,
    'layout': json.dumps({
        'width': 50,
        'height': 50,
        'elements': [
            {'type': 'text', 'field': 'name', 'x': 3, 'y': 3, 'width': 44, 'height': 8, 'fontSize': 10, 'fontWeight': 'bold'},
            {'type': 'qrcode', 'x': 15, 'y': 13, 'width': 20, 'height': 20},
            {'type': 'text', 'field': 'sku', 'x': 3, 'y': 35, 'width': 44, 'height': 6, 'fontSize': 8}
        ]
    })
}

templates = [template1, template2, template3, template4]
added = 0

print(f"Gefundene Organisationen: {len(orgs)}")

for org_id, org_name in orgs:
    # Prüfe ob bereits Templates vorhanden
    existing = conn.execute('SELECT COUNT(*) FROM label_templates WHERE organization_id = ?', (org_id,)).fetchone()[0]

    if existing > 0:
        print(f"  {org_name}: Bereits {existing} Template(s) vorhanden - ueberspringe")
        continue

    print(f"  {org_name}: Fuege {len(templates)} Templates hinzu...")

    for template in templates:
        try:
            conn.execute('''
                INSERT INTO label_templates
                (organization_id, name, description, width_mm, height_mm, layout_config, created_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ''', (
                org_id,
                template['name'],
                template['description'],
                template['width_mm'],
                template['height_mm'],
                template['layout']
            ))
            added += 1
        except Exception as e:
            print(f"    Fehler: {e}")

conn.commit()

# Verifizierung
total = conn.execute('SELECT COUNT(*) FROM label_templates').fetchone()[0]
print(f"\nErgebnis: {added} neue Template(s) hinzugefuegt")
print(f"Total in Datenbank: {total} Template(s)")

conn.close()
EOF

echo ""
echo "======================================"
echo "  Fertig!"
echo "======================================"
