// Label Designer JavaScript

let labelElements = [];
let selectedElement = null;
let draggedElementType = null;
let isDragging = false;
let isResizing = false;
let dragStartX = 0;
let dragStartY = 0;
let elementIdCounter = 0;

// Canvas-Initialisierung
document.addEventListener('DOMContentLoaded', function() {
    initCanvas();
    setupDragAndDrop();
    setupCanvasInteraction();
});

function initCanvas() {
    updateCanvasSize();
}

function updateCanvasSize() {
    const width = parseInt(document.getElementById('label-width').value);
    const height = parseInt(document.getElementById('label-height').value);

    // 1mm = ~3.78 pixels at 96 DPI
    const pixelWidth = width * 3.78;
    const pixelHeight = height * 3.78;

    const canvas = document.getElementById('label-canvas');
    canvas.style.width = pixelWidth + 'px';
    canvas.style.height = pixelHeight + 'px';

    // Raster aktualisieren
    if (document.getElementById('show-grid').checked) {
        canvas.style.backgroundImage = 'repeating-linear-gradient(0deg, #e2e8f0 0px, #e2e8f0 1px, transparent 1px, transparent 10px), repeating-linear-gradient(90deg, #e2e8f0 0px, #e2e8f0 1px, transparent 1px, transparent 10px)';
        canvas.style.backgroundSize = '10px 10px';
    }
}

function toggleGrid() {
    const canvas = document.getElementById('label-canvas');
    const showGrid = document.getElementById('show-grid').checked;

    if (showGrid) {
        canvas.style.backgroundImage = 'repeating-linear-gradient(0deg, #e2e8f0 0px, #e2e8f0 1px, transparent 1px, transparent 10px), repeating-linear-gradient(90deg, #e2e8f0 0px, #e2e8f0 1px, transparent 1px, transparent 10px)';
        canvas.style.backgroundSize = '10px 10px';
    } else {
        canvas.style.backgroundImage = 'none';
    }
}

// Drag & Drop Setup
function setupDragAndDrop() {
    const elementItems = document.querySelectorAll('.element-item');

    elementItems.forEach(item => {
        item.addEventListener('dragstart', function(e) {
            draggedElementType = {
                type: this.dataset.type,
                field: this.dataset.field
            };
            e.dataTransfer.effectAllowed = 'copy';
        });
    });

    const canvas = document.getElementById('label-canvas');

    canvas.addEventListener('dragover', function(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'copy';
    });

    canvas.addEventListener('drop', function(e) {
        e.preventDefault();

        if (!draggedElementType) return;

        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        addElementToCanvas(draggedElementType.type, draggedElementType.field, x, y);
        draggedElementType = null;
    });
}

function addElementToCanvas(type, field, x, y) {
    const elementId = 'elem-' + (elementIdCounter++);

    const element = {
        id: elementId,
        type: type,
        field: field,
        x: x,
        y: y,
        width: type === 'barcode' ? 180 : (type === 'qrcode' ? 80 : (type === 'image' ? 80 : 150)),
        height: type === 'barcode' ? 60 : (type === 'qrcode' ? 80 : (type === 'image' ? 80 : 30)),
        fontSize: 14,
        fontWeight: 'normal',
        textAlign: 'left',
        color: '#000000',
        backgroundColor: 'transparent',
        customText: field === 'custom' ? 'Freier Text' : ''
    };

    labelElements.push(element);
    renderElement(element);
}

function renderElement(element) {
    const canvas = document.getElementById('label-canvas');
    const div = document.createElement('div');
    div.id = element.id;
    div.className = 'canvas-element';
    div.style.left = element.x + 'px';
    div.style.top = element.y + 'px';
    div.style.width = element.width + 'px';
    div.style.height = element.height + 'px';
    div.style.fontSize = element.fontSize + 'px';
    div.style.fontWeight = element.fontWeight;
    div.style.textAlign = element.textAlign;
    div.style.color = element.color;
    div.style.backgroundColor = element.backgroundColor;

    // Element-Inhalt
    let content = '';
    if (element.type === 'text') {
        if (element.field === 'custom') {
            content = element.customText;
        } else {
            content = getFieldPlaceholder(element.field);
        }
        div.textContent = content;
    } else if (element.type === 'barcode') {
        div.innerHTML = '<div style="width: 100%; height: 100%; background: linear-gradient(90deg, black 2px, white 2px, white 4px, black 4px, black 6px, white 6px, white 10px, black 10px); background-size: 10px 100%; display: flex; align-items: flex-end; justify-content: center; font-size: 10px; padding-bottom: 2px; pointer-events: none;">ITEM00000001</div>';
    } else if (element.type === 'qrcode') {
        div.innerHTML = '<div style="width: 100%; height: 100%; background: white; border: 2px solid black; display: grid; grid-template-columns: repeat(5, 1fr); grid-template-rows: repeat(5, 1fr); gap: 1px; pointer-events: none;"><div style="background: black;"></div><div></div><div style="background: black;"></div><div></div><div style="background: black;"></div><div></div><div style="background: black;"></div><div></div><div style="background: black;"></div><div></div><div style="background: black;"></div><div></div><div style="background: black;"></div><div></div><div style="background: black;"></div><div></div><div style="background: black;"></div><div></div><div style="background: black;"></div><div></div><div style="background: black;"></div><div></div><div style="background: black;"></div><div></div><div style="background: black;"></div></div>';
    } else if (element.type === 'image') {
        div.innerHTML = '<div style="width: 100%; height: 100%; background: #e2e8f0; border: 2px dashed #94a3b8; display: flex; align-items: center; justify-content: center; border-radius: 4px; pointer-events: none;"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg></div>';
    }

    // Resize Handles
    div.innerHTML += `
        <div class="resize-handle nw"></div>
        <div class="resize-handle ne"></div>
        <div class="resize-handle sw"></div>
        <div class="resize-handle se"></div>
    `;

    div.addEventListener('click', function(e) {
        if (!e.target.classList.contains('resize-handle')) {
            selectElement(element.id);
        }
    });

    canvas.appendChild(div);
}

function getFieldPlaceholder(field) {
    const placeholders = {
        'name': 'Produktname',
        'sku': 'ABC-12345',
        'category': 'Kategorie',
        'location': 'Lagerort',
        'price': '€ 99.99',
        'quantity': '100 Stück'
    };
    return placeholders[field] || field;
}

function setupCanvasInteraction() {
    const canvas = document.getElementById('label-canvas');

    canvas.addEventListener('mousedown', function(e) {
        if (e.target === canvas) {
            deselectElement();
        }
    });

    // Drag & Resize Logic
    document.addEventListener('mousedown', function(e) {
        // Finde das canvas-element (entweder direkt oder als parent)
        const canvasElement = e.target.classList.contains('canvas-element')
            ? e.target
            : e.target.closest('.canvas-element');

        if (e.target.classList.contains('resize-handle')) {
            isResizing = true;
            dragStartX = e.clientX;
            dragStartY = e.clientY;
        } else if (canvasElement) {
            // Selektiere das Element wenn es noch nicht selektiert ist
            const elementId = canvasElement.id;
            const element = labelElements.find(e => e.id === elementId);
            if (element) {
                selectElement(elementId);
                isDragging = true;
                const rect = canvasElement.getBoundingClientRect();
                dragStartX = e.clientX - rect.left;
                dragStartY = e.clientY - rect.top;
            }
        }
    });

    document.addEventListener('mousemove', function(e) {
        if (isDragging && selectedElement) {
            const canvas = document.getElementById('label-canvas');
            const canvasRect = canvas.getBoundingClientRect();

            let newX = e.clientX - canvasRect.left - dragStartX;
            let newY = e.clientY - canvasRect.top - dragStartY;

            // Snap to grid
            if (document.getElementById('show-grid').checked) {
                newX = Math.round(newX / 10) * 10;
                newY = Math.round(newY / 10) * 10;
            }

            selectedElement.x = Math.max(0, Math.min(newX, canvasRect.width - selectedElement.width));
            selectedElement.y = Math.max(0, Math.min(newY, canvasRect.height - selectedElement.height));

            updateElementPosition(selectedElement);
        }

        if (isResizing && selectedElement) {
            const deltaX = e.clientX - dragStartX;
            const deltaY = e.clientY - dragStartY;

            selectedElement.width = Math.max(20, selectedElement.width + deltaX);
            selectedElement.height = Math.max(20, selectedElement.height + deltaY);

            dragStartX = e.clientX;
            dragStartY = e.clientY;

            updateElementPosition(selectedElement);
        }
    });

    document.addEventListener('mouseup', function() {
        isDragging = false;
        isResizing = false;
    });

    // Delete mit Delete/Backspace Taste
    document.addEventListener('keydown', function(e) {
        if ((e.key === 'Delete' || e.key === 'Backspace') && selectedElement) {
            e.preventDefault();
            deleteSelected();
        }
    });
}

function selectElement(elementId) {
    deselectElement();

    const element = labelElements.find(e => e.id === elementId);
    if (!element) return;

    selectedElement = element;

    const div = document.getElementById(elementId);
    div.classList.add('selected');

    showProperties(element);
}

function deselectElement() {
    if (selectedElement) {
        const div = document.getElementById(selectedElement.id);
        if (div) div.classList.remove('selected');
        selectedElement = null;
    }

    document.getElementById('properties-content').innerHTML = `
        <p style="color: var(--text-secondary); font-size: 14px; padding: 20px; text-align: center;">
            Wähle ein Element aus, um seine Eigenschaften zu bearbeiten
        </p>
    `;
}

function showProperties(element) {
    let html = '';

    if (element.type === 'text') {
        html = `
            ${element.field === 'custom' ? `
            <div class="property-group">
                <label>Text</label>
                <input type="text" value="${element.customText}" onchange="updateElementProperty('customText', this.value)">
            </div>
            ` : `
            <div class="property-group">
                <label>Feld</label>
                <select onchange="updateElementProperty('field', this.value)">
                    <option value="name" ${element.field === 'name' ? 'selected' : ''}>Artikel-Name</option>
                    <option value="sku" ${element.field === 'sku' ? 'selected' : ''}>SKU</option>
                    <option value="category" ${element.field === 'category' ? 'selected' : ''}>Kategorie</option>
                    <option value="location" ${element.field === 'location' ? 'selected' : ''}>Standort</option>
                </select>
            </div>
            `}

            <div class="property-group">
                <label>Schriftgröße (px)</label>
                <input type="number" value="${element.fontSize}" min="8" max="72" onchange="updateElementProperty('fontSize', parseInt(this.value))">
            </div>

            <div class="property-group">
                <label>Schriftstärke</label>
                <select onchange="updateElementProperty('fontWeight', this.value)">
                    <option value="normal" ${element.fontWeight === 'normal' ? 'selected' : ''}>Normal</option>
                    <option value="bold" ${element.fontWeight === 'bold' ? 'selected' : ''}>Fett</option>
                </select>
            </div>

            <div class="property-group">
                <label>Ausrichtung</label>
                <select onchange="updateElementProperty('textAlign', this.value)">
                    <option value="left" ${element.textAlign === 'left' ? 'selected' : ''}>Links</option>
                    <option value="center" ${element.textAlign === 'center' ? 'selected' : ''}>Zentriert</option>
                    <option value="right" ${element.textAlign === 'right' ? 'selected' : ''}>Rechts</option>
                </select>
            </div>

            <div class="property-group">
                <label>Textfarbe</label>
                <div class="color-input-group">
                    <input type="color" value="${element.color}" onchange="updateElementProperty('color', this.value)">
                    <input type="text" value="${element.color}" onchange="updateElementProperty('color', this.value)" style="flex: 1;">
                </div>
            </div>

            <div class="property-group">
                <label>Hintergrundfarbe</label>
                <div class="color-input-group">
                    <input type="color" value="${element.backgroundColor}" onchange="updateElementProperty('backgroundColor', this.value)">
                    <input type="text" value="${element.backgroundColor}" onchange="updateElementProperty('backgroundColor', this.value)" style="flex: 1;">
                </div>
            </div>
        `;
    } else {
        html = `
            <div class="property-group">
                <label>Typ</label>
                <input type="text" value="${element.type === 'barcode' ? 'Barcode' : (element.type === 'qrcode' ? 'QR-Code' : 'Artikel-Bild')}" disabled>
            </div>
        `;
    }

    html += `
        <div class="property-group">
            <label>Position X (px)</label>
            <input type="number" value="${Math.round(element.x)}" onchange="updateElementProperty('x', parseFloat(this.value))">
        </div>

        <div class="property-group">
            <label>Position Y (px)</label>
            <input type="number" value="${Math.round(element.y)}" onchange="updateElementProperty('y', parseFloat(this.value))">
        </div>

        <div class="property-group">
            <label>Breite (px)</label>
            <input type="number" value="${Math.round(element.width)}" min="20" onchange="updateElementProperty('width', parseFloat(this.value))">
        </div>

        <div class="property-group">
            <label>Höhe (px)</label>
            <input type="number" value="${Math.round(element.height)}" min="20" onchange="updateElementProperty('height', parseFloat(this.value))">
        </div>

        <div style="margin-top: 20px;">
            <button onclick="deleteSelected()" class="btn btn-danger" style="width: 100%;">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"/>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                </svg>
                Element löschen
            </button>
        </div>
    `;

    document.getElementById('properties-content').innerHTML = html;
}

function updateElementProperty(property, value) {
    if (!selectedElement) return;

    selectedElement[property] = value;

    // Re-render element
    const div = document.getElementById(selectedElement.id);
    if (div) {
        div.remove();
    }
    renderElement(selectedElement);
    selectElement(selectedElement.id);
}

function updateElementPosition(element) {
    const div = document.getElementById(element.id);
    if (!div) return;

    div.style.left = element.x + 'px';
    div.style.top = element.y + 'px';
    div.style.width = element.width + 'px';
    div.style.height = element.height + 'px';
}

function deleteSelected() {
    if (!selectedElement) {
        showAlert('Bitte wähle erst ein Element aus', 'error');
        return;
    }

    const index = labelElements.findIndex(e => e.id === selectedElement.id);
    if (index > -1) {
        labelElements.splice(index, 1);
    }

    const div = document.getElementById(selectedElement.id);
    if (div) div.remove();

    deselectElement();
}

function clearCanvas() {
    if (!confirm('Möchtest du wirklich alle Elemente löschen?')) return;

    labelElements = [];
    document.getElementById('label-canvas').innerHTML = '';
    deselectElement();
}

function previewLabel() {
    // Öffne Preview in neuem Fenster
    const config = {
        width: parseInt(document.getElementById('label-width').value),
        height: parseInt(document.getElementById('label-height').value),
        elements: labelElements
    };

    localStorage.setItem('labelPreviewConfig', JSON.stringify(config));
    window.open('/label-preview', '_blank', 'width=800,height=600');
}

async function saveTemplate() {
    const name = prompt('Template-Name:');
    if (!name) return;

    const config = {
        width: parseInt(document.getElementById('label-width').value),
        height: parseInt(document.getElementById('label-height').value),
        elements: labelElements
    };

    try {
        const response = await fetch('/api/label-templates', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({
                name: name,
                width_mm: config.width,
                height_mm: config.height,
                layout_config: JSON.stringify(config)
            })
        });

        const result = await response.json();

        if (result.success) {
            showAlert('Template erfolgreich gespeichert!', 'success');
        } else {
            showAlert(result.message || 'Fehler beim Speichern', 'error');
        }
    } catch (error) {
        console.error('Fehler:', error);
        showAlert('Fehler beim Speichern des Templates', 'error');
    }
}

function showAlert(message, type = 'success') {
    const container = document.getElementById('alert-container');
    const alert = document.createElement('div');
    alert.className = `alert ${type} show`;
    alert.textContent = message;
    container.appendChild(alert);

    setTimeout(() => {
        alert.classList.remove('show');
        setTimeout(() => alert.remove(), 300);
    }, 3000);
}

function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]').content;
}
