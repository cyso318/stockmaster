# Label Templates Fix & Setup

## Problem behoben ✅

**Internal Server Error beim Drucken von Custom Labels**

### Was war der Fehler?
Der Jinja2 Template-Filter `fromjson` fehlte, wodurch das `layout_config` JSON-Feld nicht geparst werden konnte.

### Lösung
Jinja2-Filter `fromjson` in `app.py` hinzugefügt (Zeile 64-70)

---

## Auf dem Server installieren

### 1. Code aktualisieren
```bash
cd ~/stockmaster
git pull
```

### 2. Standard-Templates zur Datenbank hinzufügen
```bash
chmod +x add_templates_server.sh
./add_templates_server.sh
```

### 3. Server neu starten
```bash
sudo systemctl restart stockmaster
# oder
sudo systemctl restart gunicorn
```

---

## Templates nutzen

### Weg zum Custom Label Druck:

1. **Dashboard** → Tab **"Artikel"**
2. Bei einem Artikel auf **Barcode-Symbol (⊡)** klicken
3. Im Barcode-Modal auf **"🎨 Custom Label"** klicken
4. **Template auswählen** aus der Liste:
   - Brother QL-700 Standard (62x29mm)
   - Klein & Kompakt (40x20mm)
   - Groß mit Bild (62x42mm)
   - QR-Code Variante (50x50mm)
5. **Druckvorschau** öffnet sich
6. **Strg+P** zum Drucken

---

## Neue Templates erstellen

1. **Burger-Menü (☰)** → **"Einstellungen"**
2. Klick auf **"Label Designer öffnen"**
3. Elemente per **Drag & Drop** auf das Label ziehen
4. **Eigenschaften anpassen** (Größe, Position, Schriftart)
5. **"Template speichern"** klicken
6. Name eingeben → Fertig!

---

## Verfügbare Elemente im Designer

- **Artikel-Name** - Dynamischer Text
- **SKU / Artikelnummer** - Dynamischer Text
- **Barcode** - Code128 Format
- **QR-Code** - Scanbar mit Smartphone
- **Artikel-Bild** - Foto des Artikels
- **Kategorie** - Dynamischer Text
- **Standort** - Dynamischer Text
- **Freier Text** - Eigenen Text eingeben

---

## Commits

- `47e1c8a` - Fix: Add fromjson Jinja2 filter for custom label templates
- `7716473` - Add script to create default label templates

---

## Testen

Nach dem Update sollte:
- ✅ Keine "Internal Server Error" mehr beim Custom Label Druck
- ✅ Template-Auswahl funktionieren
- ✅ 4 Standard-Templates verfügbar sein
- ✅ Druckvorschau korrekt anzeigen

Bei Problemen: Browser-Cache leeren (Strg+Shift+Delete)
