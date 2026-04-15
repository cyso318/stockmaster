// Globale Variablen
let categories = [];
let locations = [];
let items = [];
let groups = [];
let currentFilter = {};
let collapsedGroups = new Set(JSON.parse(localStorage.getItem('collapsedGroups') || '[]'));

// ============= INITIALISIERUNG =============

document.addEventListener('DOMContentLoaded', function() {
    loadDashboard();
    loadCategories();
    loadLocations();
    loadItems();

    // Backup-Status beim Laden aktualisieren
    updateBackupStatusUI();

    // Aktualisiere Backup-Status alle 5 Minuten
    setInterval(updateBackupStatusUI, 5 * 60 * 1000);

    // CSRF Token automatisch auffrischen wenn Seite wieder sichtbar wird
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            refreshCSRFToken();
        }
    });

    // CSRF Token alle 30 Minuten auffrischen
    setInterval(refreshCSRFToken, 30 * 60 * 1000);
});

// ============= HILFSFUNKTIONEN =============

function showAlert(message, type = 'success') {
    const container = document.getElementById('alert-container');
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.textContent = message;
    container.appendChild(alert);

    // Auto-dismiss nach 5 Sekunden
    setTimeout(() => {
        alert.style.opacity = '0';
        alert.style.transform = 'translateY(-20px)';
        setTimeout(() => alert.remove(), 300);
    }, 5000);
}

// Formular-Validierung mit visuellem Feedback
function validateInput(input, isValid, errorMessage = '') {
    const formGroup = input.closest('.form-group');
    if (!formGroup) return;

    // Entferne alte Fehlermeldung
    const oldError = formGroup.querySelector('.error-message');
    if (oldError) oldError.remove();

    // Entferne alte Styles
    input.classList.remove('input-error', 'input-success');

    if (!isValid) {
        input.classList.add('input-error');
        if (errorMessage) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error-message';
            errorDiv.textContent = errorMessage;
            errorDiv.style.color = 'var(--danger)';
            errorDiv.style.fontSize = '12px';
            errorDiv.style.marginTop = '4px';
            formGroup.appendChild(errorDiv);
        }
    } else {
        input.classList.add('input-success');
    }
}

// Live-Validierung für Zahlen-Inputs
function validateNumberInput(input, min = null, max = null) {
    const value = parseFloat(input.value);

    if (isNaN(value)) {
        validateInput(input, false, 'Bitte geben Sie eine gültige Zahl ein');
        return false;
    }

    if (min !== null && value < min) {
        validateInput(input, false, `Wert muss mindestens ${min} sein`);
        return false;
    }

    if (max !== null && value > max) {
        validateInput(input, false, `Wert darf höchstens ${max} sein`);
        return false;
    }

    validateInput(input, true);
    return true;
}

// Lade-Indikator für Buttons
function setButtonLoading(button, loading = true) {
    if (loading) {
        button.disabled = true;
        button.dataset.originalText = button.textContent;
        button.innerHTML = '<span class="loading-spinner"></span> Laden...';
        button.classList.add('loading');
    } else {
        button.disabled = false;
        button.textContent = button.dataset.originalText || button.textContent;
        button.classList.remove('loading');
    }
}

function openModal(modalId) {
    document.getElementById(modalId).classList.add('active');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

function switchTab(tab) {
    // Tabs aktualisieren
    document.querySelectorAll('.nav-tab').forEach(t => {
        t.classList.remove('active');
        if (t.textContent.trim().toLowerCase().includes(tab === 'dashboard' ? 'dashboard' : tab === 'items' ? 'artikel' : tab === 'categories' ? 'kategor' : tab === 'locations' ? 'standort' : tab === 'maintenance' ? 'wartung' : '___')) {
            t.classList.add('active');
        }
    });
    // Fallback: event.target wenn vorhanden
    if (typeof event !== 'undefined' && event && event.target && event.target.classList && event.target.classList.contains('nav-tab')) {
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        event.target.classList.add('active');
    }

    // Sections aktualisieren
    document.querySelectorAll('.content-section').forEach(s => s.classList.remove('active'));
    const section = document.getElementById(`${tab}-section`);
    if (section) section.classList.add('active');

    // Daten laden
    if (tab === 'items') loadItems();
    if (tab === 'categories') loadCategories();
    if (tab === 'locations') loadLocations();
    if (tab === 'maintenance') {
        if (typeof loadMaintenanceItems === 'function') loadMaintenanceItems();
        if (typeof loadMaintenanceTypes === 'function') loadMaintenanceTypes();
    }
}

async function apiCall(url, options = {}) {
    try {
        // CSRF-Token aus Meta-Tag holen
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;

        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...(csrfToken && { 'X-CSRFToken': csrfToken }),
                ...options.headers
            }
        });

        // Check if response is OK
        if (!response.ok) {
            // Try to get error message from response
            const contentType = response.headers.get('content-type');
            let errorMessage = `Server-Fehler: ${response.status}`;

            if (contentType && contentType.includes('application/json')) {
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.message || errorData.error || errorMessage;
                } catch (e) {
                    // JSON parse failed, use default message
                }
            } else {
                // HTML error page returned
                const text = await response.text();
                console.error('Server returned HTML error:', text.substring(0, 500));
            }

            // CSRF Token expired - refresh and retry
            if (response.status === 400) {
                if (errorMessage.toLowerCase().includes('csrf')) {
                    console.log('CSRF Token expired, refreshing...');
                    await refreshCSRFToken();

                    // Retry request with new token
                    const newCsrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
                    const retryResponse = await fetch(url, {
                        ...options,
                        headers: {
                            'Content-Type': 'application/json',
                            ...(newCsrfToken && { 'X-CSRFToken': newCsrfToken }),
                            ...options.headers
                        }
                    });

                    if (!retryResponse.ok) {
                        throw new Error(`Retry failed: ${retryResponse.status}`);
                    }
                    return await retryResponse.json();
                }
            }

            throw new Error(errorMessage);
        }

        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        showAlert(error.message || 'Fehler bei der Kommunikation mit dem Server', 'error');
        throw error;
    }
}

// Get current CSRF Token
function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]')?.content || '';
}

// Refresh CSRF Token
async function refreshCSRFToken() {
    try {
        const response = await fetch('/api/csrf-token');
        const data = await response.json();
        if (data.csrf_token) {
            // Update meta tag
            const metaTag = document.querySelector('meta[name="csrf-token"]');
            if (metaTag) {
                metaTag.content = data.csrf_token;
            }
            console.log('CSRF Token refreshed successfully');
        }
    } catch (error) {
        console.error('Failed to refresh CSRF token:', error);
    }
}

// ============= DASHBOARD =============

async function loadDashboard() {
    try {
        const data = await apiCall('/api/dashboard');

        // Nur setzen wenn Elemente existieren
        const statItems = document.getElementById('stat-items');
        if (statItems) statItems.textContent = data.total_items;

        const statCategories = document.getElementById('stat-categories');
        if (statCategories) statCategories.textContent = data.total_categories;

        const statLocations = document.getElementById('stat-locations');
        if (statLocations) statLocations.textContent = data.total_locations;

        const statLowStock = document.getElementById('stat-low-stock');
        if (statLowStock) statLowStock.textContent = data.low_stock_items;

        const statValue = document.getElementById('stat-value');
        if (statValue) statValue.textContent = data.total_value.toFixed(2) + ' €';
    } catch (error) {
        console.error('Dashboard load error:', error);
    }
}

// ============= KATEGORIEN =============

async function loadCategories() {
    try {
        categories = await apiCall('/api/categories');
        renderCategories();
        updateCategorySelects();
    } catch (error) {
        console.error('Categories load error:', error);
    }
}

function renderCategories() {
    const container = document.getElementById('categories-list');

    if (categories.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>Noch keine Kategorien vorhanden</p></div>';
        return;
    }

    let html = `
        <div class="modern-table">
            <div class="table-header-row">
                <div class="table-cell header-cell" style="flex: 2; min-width: 150px;">Name</div>
                <div class="table-cell header-cell" style="flex: 3; min-width: 200px;">Beschreibung</div>
                <div class="table-cell header-cell" style="width: 120px;">Erstellt</div>
                <div class="table-cell header-cell" style="width: 120px; text-align: center;">Aktionen</div>
            </div>
    `;

    categories.forEach(cat => {
        html += `
            <div class="table-row" onclick="editCategory(${cat.id})">
                <div class="table-cell" style="flex: 2; min-width: 150px;">
                    <strong>${cat.name}</strong>
                </div>
                <div class="table-cell" style="flex: 3; min-width: 200px;">
                    <span class="text-muted">${cat.description || '-'}</span>
                </div>
                <div class="table-cell" style="width: 120px;">
                    ${new Date(cat.created_at).toLocaleDateString('de-DE')}
                </div>
                <div class="table-cell table-actions" style="width: 120px;" onclick="event.stopPropagation();">
                    <button class="btn-table-action btn-edit" onclick="editCategory(${cat.id})" title="Bearbeiten">✎</button>
                    <button class="btn-table-action btn-delete" onclick="deleteCategory(${cat.id})" title="Löschen">🗑</button>
                </div>
            </div>
        `;
    });

    html += '</div>';
    container.innerHTML = html;
}

function updateCategorySelects() {
    const selects = ['item-category', 'filter-category'];
    selects.forEach(selectId => {
        const select = document.getElementById(selectId);
        if (!select) return;
        
        const currentValue = select.value;
        select.innerHTML = '<option value="">-- Keine Kategorie --</option>';
        
        categories.forEach(cat => {
            select.innerHTML += `<option value="${cat.id}">${cat.name}</option>`;
        });
        
        if (currentValue) select.value = currentValue;
    });
}

function openCategoryModal(id = null) {
    if (id) {
        const category = categories.find(c => c.id === id);
        document.getElementById('category-id').value = category.id;
        document.getElementById('category-name').value = category.name;
        document.getElementById('category-description').value = category.description || '';
    } else {
        document.getElementById('category-form').reset();
        document.getElementById('category-id').value = '';
    }
    openModal('category-modal');
}

function editCategory(id) {
    openCategoryModal(id);
}

async function saveCategory(event) {
    event.preventDefault();
    
    const id = document.getElementById('category-id').value;
    const data = {
        name: document.getElementById('category-name').value,
        description: document.getElementById('category-description').value
    };
    
    try {
        if (id) {
            await apiCall(`/api/categories/${id}`, {
                method: 'PUT',
                body: JSON.stringify(data)
            });
            showAlert('Kategorie aktualisiert');
        } else {
            await apiCall('/api/categories', {
                method: 'POST',
                body: JSON.stringify(data)
            });
            showAlert('Kategorie erstellt');
        }
        
        closeModal('category-modal');
        loadCategories();
        loadDashboard();
    } catch (error) {
        showAlert('Fehler beim Speichern der Kategorie', 'error');
    }
}

async function deleteCategory(id) {
    if (!confirm('Kategorie wirklich löschen?')) return;
    
    try {
        await apiCall(`/api/categories/${id}`, { method: 'DELETE' });
        showAlert('Kategorie gelöscht');
        loadCategories();
        loadDashboard();
    } catch (error) {
        showAlert('Fehler beim Löschen der Kategorie', 'error');
    }
}

// ============= STANDORTE =============

async function loadLocations() {
    try {
        locations = await apiCall('/api/locations');
        renderLocations();
        updateLocationSelects();
    } catch (error) {
        console.error('Locations load error:', error);
    }
}

function renderLocations() {
    const container = document.getElementById('locations-list');

    if (locations.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>Noch keine Standorte vorhanden</p></div>';
        return;
    }

    let html = `
        <div class="modern-table">
            <div class="table-header-row">
                <div class="table-cell header-cell" style="flex: 2; min-width: 150px;">Name</div>
                <div class="table-cell header-cell" style="flex: 3; min-width: 200px;">Beschreibung</div>
                <div class="table-cell header-cell" style="width: 120px;">Erstellt</div>
                <div class="table-cell header-cell" style="width: 120px; text-align: center;">Aktionen</div>
            </div>
    `;

    locations.forEach(loc => {
        html += `
            <div class="table-row" onclick="editLocation(${loc.id})">
                <div class="table-cell" style="flex: 2; min-width: 150px;">
                    <strong>${loc.name}</strong>
                </div>
                <div class="table-cell" style="flex: 3; min-width: 200px;">
                    <span class="text-muted">${loc.description || '-'}</span>
                </div>
                <div class="table-cell" style="width: 120px;">
                    ${new Date(loc.created_at).toLocaleDateString('de-DE')}
                </div>
                <div class="table-cell table-actions" style="width: 120px;" onclick="event.stopPropagation();">
                    <button class="btn-table-action btn-edit" onclick="editLocation(${loc.id})" title="Bearbeiten">✎</button>
                    <button class="btn-table-action btn-delete" onclick="deleteLocation(${loc.id})" title="Löschen">🗑</button>
                </div>
            </div>
        `;
    });

    html += '</div>';
    container.innerHTML = html;
}

function updateLocationSelects() {
    const selects = ['item-location', 'filter-location'];
    selects.forEach(selectId => {
        const select = document.getElementById(selectId);
        if (!select) return;
        
        const currentValue = select.value;
        select.innerHTML = '<option value="">-- Kein Standort --</option>';
        
        locations.forEach(loc => {
            select.innerHTML += `<option value="${loc.id}">${loc.name}</option>`;
        });
        
        if (currentValue) select.value = currentValue;
    });
}

function openLocationModal(id = null) {
    if (id) {
        const location = locations.find(l => l.id === id);
        document.getElementById('location-id').value = location.id;
        document.getElementById('location-name').value = location.name;
        document.getElementById('location-description').value = location.description || '';
    } else {
        document.getElementById('location-form').reset();
        document.getElementById('location-id').value = '';
    }
    openModal('location-modal');
}

function editLocation(id) {
    openLocationModal(id);
}

async function saveLocation(event) {
    event.preventDefault();
    
    const id = document.getElementById('location-id').value;
    const data = {
        name: document.getElementById('location-name').value,
        description: document.getElementById('location-description').value
    };
    
    try {
        if (id) {
            await apiCall(`/api/locations/${id}`, {
                method: 'PUT',
                body: JSON.stringify(data)
            });
            showAlert('Standort aktualisiert');
        } else {
            await apiCall('/api/locations', {
                method: 'POST',
                body: JSON.stringify(data)
            });
            showAlert('Standort erstellt');
        }
        
        closeModal('location-modal');
        loadLocations();
        loadDashboard();
    } catch (error) {
        showAlert('Fehler beim Speichern des Standorts', 'error');
    }
}

async function deleteLocation(id) {
    if (!confirm('Standort wirklich löschen?')) return;
    
    try {
        await apiCall(`/api/locations/${id}`, { method: 'DELETE' });
        showAlert('Standort gelöscht');
        loadLocations();
        loadDashboard();
    } catch (error) {
        showAlert('Fehler beim Löschen des Standorts', 'error');
    }
}

// ============= ARTIKEL =============

async function loadItems(filters = {}) {
    try {
        const params = new URLSearchParams(filters);
        items = await apiCall(`/api/items?${params}`);
        groups = items.filter(i => i.is_group);
        updateGroupSelects();
        renderItems();
    } catch (error) {
        console.error('Items load error:', error);
    }
}

function updateGroupSelects() {
    const selects = ['item-group', 'filter-group'];
    selects.forEach(selectId => {
        const select = document.getElementById(selectId);
        if (!select) return;
        const currentValue = select.value;
        select.innerHTML = '<option value="">-- Keine Gruppe --</option>';
        groups.forEach(g => {
            select.innerHTML += `<option value="${g.id}">${g.name}</option>`;
        });
        if (currentValue) select.value = currentValue;
    });
}

function toggleGroup(groupId) {
    if (collapsedGroups.has(groupId)) {
        collapsedGroups.delete(groupId);
    } else {
        collapsedGroups.add(groupId);
    }
    localStorage.setItem('collapsedGroups', JSON.stringify([...collapsedGroups]));
    renderItems();
}

function toggleGroupFields() {
    const isGroup = document.getElementById('item-is-group').checked;
    const groupSelectContainer = document.getElementById('group-select-container');
    if (groupSelectContainer) {
        groupSelectContainer.style.display = isGroup ? 'none' : '';
    }
}

function openGroupModal() {
    openItemModal();
    document.getElementById('item-is-group').checked = true;
    toggleGroupFields();
    document.getElementById('item-modal-title').textContent = 'Neue Gruppe / Container';
}

// View Mode (Karten oder Tabelle)
let itemsViewMode = localStorage.getItem('itemsViewMode') || 'cards';

function toggleItemsView() {
    itemsViewMode = itemsViewMode === 'table' ? 'cards' : 'table';
    localStorage.setItem('itemsViewMode', itemsViewMode);

    const btn = document.getElementById('view-toggle-btn');
    if (itemsViewMode === 'cards') {
        btn.innerHTML = `
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="3" width="7" height="7"/>
                <rect x="14" y="3" width="7" height="7"/>
                <rect x="14" y="14" width="7" height="7"/>
                <rect x="3" y="14" width="7" height="7"/>
            </svg>
            Karten`;
    } else {
        btn.innerHTML = `
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="3" y1="12" x2="21" y2="12"/>
                <line x1="3" y1="6" x2="21" y2="6"/>
                <line x1="3" y1="18" x2="21" y2="18"/>
            </svg>
            Tabelle`;
    }

    renderItems();
}

function renderItems() {
    const container = document.getElementById('items-list');

    if (items.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <svg width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
                    <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
                    <line x1="12" y1="22.08" x2="12" y2="12"/>
                </svg>
                <p>Keine Artikel gefunden</p>
                <button onclick="openItemModal()" style="margin-top: 16px;">+ Ersten Artikel anlegen</button>
            </div>`;
        return;
    }

    // Prüfen ob Suche aktiv ist - dann flach anzeigen
    const searchEl = document.getElementById('search-items');
    const isSearchActive = searchEl && searchEl.value.trim().length > 0;

    // Items in Gruppen organisieren (nur wenn keine Suche aktiv)
    let renderList = [];
    if (!isSearchActive) {
        const groupItems = items.filter(i => i.is_group);
        const ungroupedItems = items.filter(i => !i.is_group && !i.group_id);
        const groupedChildren = {};
        items.forEach(i => {
            if (i.group_id) {
                if (!groupedChildren[i.group_id]) groupedChildren[i.group_id] = [];
                groupedChildren[i.group_id].push(i);
            }
        });

        groupItems.forEach(group => {
            const children = groupedChildren[group.id] || [];
            renderList.push({ type: 'group-header', item: group, childCount: children.length });
            if (!collapsedGroups.has(group.id)) {
                children.forEach(child => {
                    renderList.push({ type: 'group-child', item: child });
                });
            }
        });
        ungroupedItems.forEach(item => {
            renderList.push({ type: 'standalone', item: item });
        });
    } else {
        // Flache Anzeige bei Suche (Gruppen-Items ausblenden)
        items.filter(i => !i.is_group).forEach(item => {
            renderList.push({ type: 'standalone', item: item });
        });
    }

    // Karten-Ansicht
    if (itemsViewMode === 'cards') {
        let html = '<div class="items-grid">';

        renderList.forEach(entry => {
            if (entry.type === 'group-header') {
                const isCollapsed = collapsedGroups.has(entry.item.id);
                html += `
                    <div class="group-header-card" onclick="toggleGroup(${entry.item.id})">
                        <div class="group-header-content">
                            <span class="group-toggle-icon">${isCollapsed ? '&#9654;' : '&#9660;'}</span>
                            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--primary);">
                                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
                                <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
                                <line x1="12" y1="22.08" x2="12" y2="12"/>
                            </svg>
                            <span class="group-name">${entry.item.name}</span>
                            <span class="group-count">${entry.childCount} Artikel</span>
                            ${entry.item.location_name ? `<span class="group-location">${entry.item.location_name}</span>` : ''}
                        </div>
                        <div class="group-actions" onclick="event.stopPropagation();">
                            <button class="btn btn-icon" onclick="showQRCode(${entry.item.id})" style="background: #17a2b8; color: white;" title="Barcode">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <rect x="3" y="3" width="18" height="18" rx="2"/>
                                </svg>
                            </button>
                            <button class="btn btn-icon btn-secondary" onclick="editItem(${entry.item.id})" title="Bearbeiten">&#9998;</button>
                            <button class="btn btn-icon btn-danger" onclick="deleteItem(${entry.item.id})" title="Loeschen">&#128465;</button>
                        </div>
                    </div>
                `;
                return;
            }

            const item = entry.item;
            const isChild = entry.type === 'group-child';
            const stockClass = item.quantity === 0 ? 'stock-out' :
                              item.quantity <= item.min_quantity ? 'stock-low' : 'stock-ok';

            const stockIcon = item.quantity === 0 ? '0' :
                             item.quantity <= item.min_quantity ? '!' : '&#10003;';

            const stockText = item.quantity === 0 ? 'Nicht verfuegbar' :
                             item.quantity <= item.min_quantity ? 'Niedriger Bestand' : 'Auf Lager';

            const imageHtml = item.image_path
                ? `<img src="/static/uploads/items/${item.image_path}" alt="${item.name}">`
                : `<div class="item-card-image-placeholder">&#128230;</div>`;

            html += `
                <div class="item-card ${isChild ? 'group-child-card' : ''}">
                    <div class="item-card-image">
                        ${imageHtml}
                        ${item.sku ? `<div class="item-card-badge">${item.sku}</div>` : ''}
                    </div>
                    <div class="item-card-body">
                        <div class="item-card-header">
                            <div style="flex: 1;">
                                <div class="item-card-title">${item.name}</div>
                                ${item.sku ? `<div class="item-card-sku">${item.sku}</div>` : ''}
                            </div>
                            <div class="item-card-price">${item.price.toFixed(2)} &euro;</div>
                        </div>

                        <div class="item-card-info">
                            ${item.category_name ? `
                                <div class="item-card-info-row">
                                    <span class="item-card-info-label">
                                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
                                        </svg>
                                        Kategorie
                                    </span>
                                    <span class="item-card-info-value">${item.category_name}</span>
                                </div>
                            ` : ''}
                            ${item.location_name ? `
                                <div class="item-card-info-row">
                                    <span class="item-card-info-label">
                                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
                                            <circle cx="12" cy="10" r="3"/>
                                        </svg>
                                        Standort
                                    </span>
                                    <span class="item-card-info-value">${item.location_name}</span>
                                </div>
                            ` : ''}
                            ${item.group_name ? `
                                <div class="item-card-info-row">
                                    <span class="item-card-info-label">
                                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
                                            <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
                                            <line x1="12" y1="22.08" x2="12" y2="12"/>
                                        </svg>
                                        Gruppe
                                    </span>
                                    <span class="item-card-info-value">${item.group_name}</span>
                                </div>
                            ` : ''}
                        </div>

                        <div class="item-card-stock ${stockClass}">
                            <div class="item-card-stock-icon">${stockIcon}</div>
                            <div style="flex: 1;">
                                <div class="item-card-stock-text">${stockText}</div>
                                <div style="font-size: 12px; color: var(--text-tertiary); margin-top: 2px;">
                                    ${item.quantity} ${item.unit} ${item.min_quantity ? `(Min: ${item.min_quantity})` : ''}
                                </div>
                            </div>
                        </div>

                        <div class="item-card-actions">
                            <button class="btn btn-icon btn-success" onclick="openMovementModal(${item.id}, 'in')" title="Einbuchen">+</button>
                            <button class="btn btn-icon btn-danger" onclick="openMovementModal(${item.id}, 'out')" title="Ausbuchen">&minus;</button>
                            <button class="btn btn-icon" onclick="showQRCode(${item.id})" style="background: #17a2b8; color: white;" title="Barcode">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <rect x="3" y="3" width="18" height="18" rx="2"/>
                                </svg>
                            </button>
                            <button class="btn btn-icon btn-secondary" onclick="editItem(${item.id})" title="Bearbeiten">&#9998;</button>
                            <button class="btn btn-icon btn-danger" onclick="deleteItem(${item.id})" title="Loeschen">&#128465;</button>
                        </div>
                    </div>
                </div>
            `;
        });

        html += '</div>';
        container.innerHTML = html;
    }
    // Tabellen-Ansicht
    else {
        let html = `
            <div class="modern-table">
                <div class="table-header-row">
                    <div class="table-cell header-cell" style="width: 80px;">Artikel</div>
                    <div class="table-cell header-cell" style="flex: 2; min-width: 200px;">Details</div>
                    <div class="table-cell header-cell" style="width: 140px;">Kategorie</div>
                    <div class="table-cell header-cell" style="width: 140px;">Standort</div>
                    <div class="table-cell header-cell" style="width: 120px; text-align: center;">Bestand</div>
                    <div class="table-cell header-cell" style="width: 100px; text-align: right;">Preis</div>
                    <div class="table-cell header-cell" style="width: 200px; text-align: center;">Aktionen</div>
                </div>
        `;

        renderList.forEach(entry => {
            if (entry.type === 'group-header') {
                const isCollapsed = collapsedGroups.has(entry.item.id);
                html += `
                    <div class="table-row group-row" onclick="toggleGroup(${entry.item.id})">
                        <div class="table-cell" style="width: 80px;">
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--primary);">
                                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
                                <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
                                <line x1="12" y1="22.08" x2="12" y2="12"/>
                            </svg>
                        </div>
                        <div class="table-cell" style="flex: 2; min-width: 200px;">
                            <span class="group-toggle-icon">${isCollapsed ? '&#9654;' : '&#9660;'}</span>
                            <strong style="margin-left: 6px;">${entry.item.name}</strong>
                            <span class="group-count-badge">${entry.childCount} Artikel</span>
                        </div>
                        <div class="table-cell" style="width: 140px;">
                            ${entry.item.category_name || '<span class="text-muted">-</span>'}
                        </div>
                        <div class="table-cell" style="width: 140px;">
                            ${entry.item.location_name || '<span class="text-muted">-</span>'}
                        </div>
                        <div class="table-cell" style="width: 120px; text-align: center;">
                            <span class="text-muted">-</span>
                        </div>
                        <div class="table-cell" style="width: 100px; text-align: right;">
                            <span class="text-muted">-</span>
                        </div>
                        <div class="table-cell table-actions" style="width: 200px;" onclick="event.stopPropagation();">
                            <button class="btn-table-action btn-info" onclick="showQRCode(${entry.item.id})" title="Barcode anzeigen">&#8865;</button>
                            <button class="btn-table-action btn-edit" onclick="editItem(${entry.item.id})" title="Bearbeiten">&#9998;</button>
                            <button class="btn-table-action btn-delete" onclick="deleteItem(${entry.item.id})" title="Loeschen">&#128465;</button>
                        </div>
                    </div>
                `;
                return;
            }

            const item = entry.item;
            const isChild = entry.type === 'group-child';
            const stockClass = item.quantity === 0 ? 'badge-danger' :
                              item.quantity <= item.min_quantity ? 'badge-warning' : 'badge-success';

            const stockIcon = item.quantity === 0 ? '&#10005;' :
                             item.quantity <= item.min_quantity ? '&#9888;' : '&#10003;';

            const imageHtml = item.image_path
                ? `<img src="/static/uploads/items/${item.image_path}" alt="${item.name}" class="table-item-image">`
                : `<div class="table-item-image-placeholder">
                     <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                       <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
                     </svg>
                   </div>`;

            html += `
                <div class="table-row ${isChild ? 'group-child-row' : ''}" onclick="editItem(${item.id})">
                    <div class="table-cell" style="width: 80px;">
                        ${imageHtml}
                    </div>
                    <div class="table-cell" style="flex: 2; min-width: 200px;">
                        <div class="item-name">${item.name}</div>
                        ${item.sku ? `<div class="item-sku">SKU: ${item.sku}</div>` : ''}
                        ${item.description ? `<div class="item-description">${item.description}</div>` : ''}
                    </div>
                    <div class="table-cell" style="width: 140px;">
                        ${item.category_name ? `
                            <div class="table-badge">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
                                </svg>
                                ${item.category_name}
                            </div>
                        ` : '<span class="text-muted">-</span>'}
                    </div>
                    <div class="table-cell" style="width: 140px;">
                        ${item.location_name ? `
                            <div class="table-badge">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
                                    <circle cx="12" cy="10" r="3"/>
                                </svg>
                                ${item.location_name}
                            </div>
                        ` : '<span class="text-muted">-</span>'}
                    </div>
                    <div class="table-cell" style="width: 120px; text-align: center;">
                        <div class="stock-indicator ${stockClass}">
                            <span class="stock-icon">${stockIcon}</span>
                            <span class="stock-value">${item.quantity} ${item.unit}</span>
                        </div>
                        ${item.min_quantity ? `<div class="stock-min">Min: ${item.min_quantity}</div>` : ''}
                    </div>
                    <div class="table-cell" style="width: 100px; text-align: right;">
                        <div class="item-price">${item.price.toFixed(2)} &euro;</div>
                    </div>
                    <div class="table-cell table-actions" style="width: 200px;" onclick="event.stopPropagation();">
                        <button class="btn-table-action btn-success" onclick="openMovementModal(${item.id}, 'in')" title="Einbuchen">+</button>
                        <button class="btn-table-action btn-danger" onclick="openMovementModal(${item.id}, 'out')" title="Ausbuchen">&minus;</button>
                        <button class="btn-table-action btn-info" onclick="showQRCode(${item.id})" title="Barcode anzeigen">&#8865;</button>
                        <button class="btn-table-action btn-edit" onclick="editItem(${item.id})" title="Bearbeiten">&#9998;</button>
                        <button class="btn-table-action btn-delete" onclick="deleteItem(${item.id})" title="Loeschen">&#128465;</button>
                    </div>
                </div>
            `;
        });

        html += '</div>';
        container.innerHTML = html;
    }
}

function searchItems(filterType = null) {
    const filters = {};

    const search = document.getElementById('search-items').value;
    if (search) filters.search = search;

    const category = document.getElementById('filter-category').value;
    if (category) filters.category = category;

    const location = document.getElementById('filter-location').value;
    if (location) filters.location = location;

    const groupEl = document.getElementById('filter-group');
    const group = groupEl ? groupEl.value : '';
    if (group) filters.group = group;

    if (filterType === 'low_stock') {
        filters.low_stock = '1';
    }

    loadItems(filters);
}

function openItemModal(id = null) {
    if (id) {
        const item = items.find(i => i.id === id);
        document.getElementById('item-modal-title').textContent = 'Artikel bearbeiten';
        document.getElementById('item-id').value = item.id;
        document.getElementById('item-sku').value = item.sku || '';
        document.getElementById('item-name').value = item.name;
        const barcodeEl = document.getElementById('item-barcode');
        if (barcodeEl) barcodeEl.value = item.barcode || '';
        document.getElementById('item-description').value = item.description || '';
        document.getElementById('item-category').value = item.category_id || '';
        document.getElementById('item-location').value = item.location_id || '';
        document.getElementById('item-quantity').value = item.quantity;
        document.getElementById('item-unit').value = item.unit;
        document.getElementById('item-min-quantity').value = item.min_quantity;
        document.getElementById('item-price').value = item.price;
        document.getElementById('item-supplier').value = item.supplier || '';
        document.getElementById('item-notes').value = item.notes || '';

        // Bild-Sektion anzeigen und aktuelles Bild laden
        const imageSection = document.getElementById('image-section');
        const currentImageContainer = document.getElementById('current-image-container');
        const currentImage = document.getElementById('current-item-image');

        imageSection.style.display = 'block';

        if (item.image_path) {
            currentImage.src = `/static/uploads/items/${item.image_path}`;
            currentImageContainer.style.display = 'block';
        } else {
            currentImageContainer.style.display = 'none';
        }

        // Vorschau zurücksetzen
        document.getElementById('image-preview').style.display = 'none';
        document.getElementById('item-image-upload').value = '';

        // Gruppen-Felder setzen
        const isGroupEl = document.getElementById('item-is-group');
        const groupEl = document.getElementById('item-group');
        if (isGroupEl) isGroupEl.checked = !!item.is_group;
        if (groupEl) groupEl.value = item.group_id || '';
        toggleGroupFields();

        // Wartungspläne laden
        if (typeof loadItemSchedules === 'function') {
            loadItemSchedules(item.id);
        }
    } else {
        document.getElementById('item-modal-title').textContent = 'Neuer Artikel';
        document.getElementById('item-form').reset();
        document.getElementById('item-id').value = '';
        document.getElementById('item-unit').value = 'Stück';

        // Gruppen-Felder zurücksetzen
        const isGroupEl = document.getElementById('item-is-group');
        const groupEl = document.getElementById('item-group');
        if (isGroupEl) isGroupEl.checked = false;
        if (groupEl) groupEl.value = '';
        toggleGroupFields();

        // Bild-Sektion anzeigen (auch für neue Artikel)
        document.getElementById('image-section').style.display = 'block';
        document.getElementById('current-image-container').style.display = 'none';
        document.getElementById('image-preview').style.display = 'none';

        // Wartungspläne zurücksetzen
        if (typeof loadItemSchedules === 'function') {
            loadItemSchedules(null);
        }
    }
    openModal('item-modal');
}

function editItem(id) {
    openItemModal(id);
}

async function saveItem(event) {
    event.preventDefault();

    const id = document.getElementById('item-id').value;
    const isGroupEl = document.getElementById('item-is-group');
    const groupEl = document.getElementById('item-group');
    const data = {
        sku: document.getElementById('item-sku').value,
        name: document.getElementById('item-name').value,
        barcode: document.getElementById('item-barcode')?.value || null,
        description: document.getElementById('item-description').value,
        category_id: document.getElementById('item-category').value || null,
        location_id: document.getElementById('item-location').value || null,
        quantity: parseInt(document.getElementById('item-quantity').value),
        unit: document.getElementById('item-unit').value,
        min_quantity: parseInt(document.getElementById('item-min-quantity').value),
        price: parseFloat(document.getElementById('item-price').value),
        supplier: document.getElementById('item-supplier').value,
        notes: document.getElementById('item-notes').value,
        is_group: isGroupEl ? isGroupEl.checked : false,
        group_id: groupEl ? (groupEl.value || null) : null
    };

    try {
        let itemId = id;

        if (id) {
            await apiCall(`/api/items/${id}`, {
                method: 'PUT',
                body: JSON.stringify(data)
            });

            // Bild hochladen falls ausgewählt
            const fileInput = document.getElementById('item-image-upload');
            if (fileInput && fileInput.files.length > 0) {
                await uploadItemImage(id);
            }

            showAlert('Artikel aktualisiert');
        } else {
            const result = await apiCall('/api/items', {
                method: 'POST',
                body: JSON.stringify(data)
            });

            itemId = result.id;

            // Bild hochladen falls ausgewählt (nach Artikel-Erstellung)
            const fileInput = document.getElementById('item-image-upload');
            if (fileInput && fileInput.files.length > 0 && itemId) {
                await uploadItemImage(itemId);
            }

            showAlert('Artikel erstellt');
        }

        closeModal('item-modal');
        loadItems();
        loadDashboard();
    } catch (error) {
        showAlert('Fehler beim Speichern des Artikels', 'error');
    }
}

async function deleteItem(id) {
    if (!confirm('Artikel wirklich löschen?')) return;
    
    try {
        await apiCall(`/api/items/${id}`, { method: 'DELETE' });
        showAlert('Artikel gelöscht');
        loadItems();
        loadDashboard();
    } catch (error) {
        showAlert('Fehler beim Löschen des Artikels', 'error');
    }
}

// ============= BEWEGUNGEN =============

function openMovementModal(itemId, type) {
    const item = items.find(i => i.id === itemId);

    document.getElementById('movement-item-id').value = itemId;
    document.getElementById('movement-type').value = type;
    document.getElementById('movement-item-name').value = item.name;
    document.getElementById('movement-current-qty').value = `${item.quantity} ${item.unit}`;

    document.getElementById('movement-modal-title').textContent =
        type === 'in' ? '📦 Einbuchen' : '📤 Ausbuchen';

    const submitBtn = document.getElementById('movement-submit-btn');
    submitBtn.className = type === 'in' ? 'btn btn-success' : 'btn btn-danger';

    // Sammelschein-Button nur bei Ausbuchung anzeigen
    const cartBtn = document.getElementById('movement-cart-btn');
    cartBtn.style.display = type === 'out' ? 'inline-flex' : 'none';

    document.getElementById('movement-submit-btn').style.display = '';
    document.getElementById('movement-form').reset();
    document.getElementById('movement-item-id').value = itemId;
    document.getElementById('movement-type').value = type;

    openModal('movement-modal');
}

async function saveMovement(event) {
    event.preventDefault();

    const itemId = document.getElementById('movement-item-id').value;
    const moveType = document.getElementById('movement-type').value;
    const data = {
        type: moveType,
        quantity: parseInt(document.getElementById('movement-quantity').value),
        reference: document.getElementById('movement-reference').value,
        notes: document.getElementById('movement-notes').value
    };

    try {
        const result = await apiCall(`/api/items/${itemId}/move`, {
            method: 'POST',
            body: JSON.stringify(data)
        });

        loadItems();
        loadDashboard();

        if (moveType === 'out' && result.slip_id) {
            closeModal('movement-modal');
            window.open(`/slip/${result.slip_id}`, '_blank');
        } else {
            showAlert(result.message);
            closeModal('movement-modal');
        }
    } catch (error) {
        showAlert('Fehler beim Buchen der Bewegung', 'error');
    }
}

// ============= SAMMELSCHEIN (WARENKORB) =============

let cart = [];  // [{item_id, item_name, sku, unit, quantity, notes}]

function updateCartFab() {
    const fab = document.getElementById('cart-fab');
    const badge = document.getElementById('cart-badge');
    if (cart.length > 0) {
        fab.style.display = 'flex';
        badge.textContent = cart.length;
    } else {
        fab.style.display = 'none';
    }
}

function addToCart() {
    const itemId = parseInt(document.getElementById('movement-item-id').value);
    const quantity = parseInt(document.getElementById('movement-quantity').value);
    const notes = document.getElementById('movement-notes').value;
    const item = items.find(i => i.id === itemId);

    if (!quantity || quantity < 1) {
        showAlert('Bitte Menge eingeben', 'error');
        return;
    }

    // Prüfen ob Artikel bereits im Warenkorb
    const existing = cart.find(c => c.item_id === itemId);
    if (existing) {
        existing.quantity += quantity;
        if (notes) existing.notes = notes;
    } else {
        cart.push({
            item_id: itemId,
            item_name: item ? item.name : `Artikel #${itemId}`,
            sku: item ? item.sku : '',
            unit: item ? item.unit : 'Stk.',
            quantity,
            notes
        });
    }

    updateCartFab();
    closeModal('movement-modal');
    showAlert(`"${item ? item.name : 'Artikel'}" zum Sammelschein hinzugefügt`);
}

function openCartModal() {
    renderCartItems();
    openModal('cart-modal');
}

function renderCartItems() {
    const container = document.getElementById('cart-items-list');
    if (cart.length === 0) {
        container.innerHTML = '<p style="color: var(--text-secondary); text-align:center; padding: 20px;">Keine Positionen im Sammelschein.</p>';
        return;
    }

    let html = `<table style="width:100%; border-collapse:collapse; font-size:13px;">
        <thead>
            <tr style="border-bottom: 2px solid var(--border-color);">
                <th style="text-align:left; padding:8px 4px;">Artikel</th>
                <th style="text-align:left; padding:8px 4px;">SKU</th>
                <th style="text-align:right; padding:8px 4px;">Menge</th>
                <th style="text-align:left; padding:8px 4px;">Einheit</th>
                <th style="padding:8px 4px;"></th>
            </tr>
        </thead>
        <tbody>`;

    cart.forEach((entry, idx) => {
        html += `<tr style="border-bottom: 1px solid var(--border-color);">
            <td style="padding:8px 4px;">${entry.item_name}</td>
            <td style="padding:8px 4px; color: var(--text-secondary);">${entry.sku || '—'}</td>
            <td style="padding:8px 4px; text-align:right; font-weight:bold;">${entry.quantity}</td>
            <td style="padding:8px 4px;">${entry.unit || 'Stk.'}</td>
            <td style="padding:8px 4px;">
                <button onclick="removeFromCart(${idx})" style="background:none; border:none; color: var(--danger); cursor:pointer; font-size:16px;" title="Entfernen">×</button>
            </td>
        </tr>`;
        if (entry.notes) {
            html += `<tr><td colspan="5" style="padding:2px 4px 8px 16px; color: var(--text-secondary); font-size:11px; font-style:italic;">${entry.notes}</td></tr>`;
        }
    });

    html += `</tbody></table>`;
    container.innerHTML = html;
}

function removeFromCart(idx) {
    cart.splice(idx, 1);
    updateCartFab();
    renderCartItems();
}

function clearCart() {
    cart = [];
    updateCartFab();
    renderCartItems();
}

async function submitCart() {
    if (cart.length === 0) {
        showAlert('Keine Positionen im Sammelschein', 'error');
        return;
    }

    const reference = document.getElementById('cart-reference').value;
    const notes = document.getElementById('cart-notes').value;

    const btn = document.getElementById('cart-submit-btn');
    btn.disabled = true;
    btn.textContent = 'Wird verarbeitet...';

    try {
        const result = await apiCall('/api/withdrawals/batch', {
            method: 'POST',
            body: JSON.stringify({
                items: cart.map(c => ({ item_id: c.item_id, quantity: c.quantity, notes: c.notes })),
                reference,
                notes
            })
        });

        clearCart();
        closeModal('cart-modal');
        loadItems();
        loadDashboard();

        if (result.slip_id) {
            window.open(`/slip/${result.slip_id}`, '_blank');
        }
    } catch (error) {
        showAlert('Fehler beim Ausbuchen', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Alle ausbuchen & Schein erstellen';
    }
}

// ============= CLOUD SYNC & EXPORT =============

// Sync/Backup entfernt – Daten liegen in Supabase (cloud-nativ)
function syncToCloud() {
    showAlert('Daten werden in Supabase gespeichert – kein manuelles Backup nötig.', 'success');
}
async function getBackupStatus() { return null; }
async function updateBackupStatusUI() {}

function exportCSV() {
    window.location.href = '/api/export/csv';
}

// ============= QR-CODE FUNKTIONEN =============

async function showQRCode(itemId) {
    try {
        const result = await apiCall(`/api/items/${itemId}/barcode-base64`);

        if (result.success) {
            // Finde das Item für Kategorie-Anzeige
            const item = items.find(i => i.id === itemId);
            const categoryHtml = item && item.category_name
                ? `<div style="color: #6366f1; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; font-size: 13px; margin-bottom: 8px;">${item.category_name}</div>`
                : '';
            const itemName = item ? item.name : 'Artikel';

            // Modal für Barcode erstellen
            const modal = document.createElement('div');
            modal.className = 'modal active';
            modal.innerHTML = `
                <div class="modal-content" style="max-width: 500px;">
                    <div class="modal-header">
                        <h3>Barcode für ${itemName}</h3>
                        <span class="close" onclick="this.parentElement.parentElement.parentElement.remove()">&times;</span>
                    </div>
                    <div style="text-align: center; padding: 20px;">
                        ${categoryHtml}
                        <img src="${result.barcode}" style="width: 100%; max-width: 400px; height: auto; margin: 20px auto; display: block;">
                        <p style="margin: 20px 0; color: #666;">Scannen Sie diesen Barcode mit einem Scanner</p>
                        <div style="display: flex; gap: 10px; justify-content: center; flex-wrap: wrap;">
                            <button onclick="downloadBarcode(${itemId})" class="btn">💾 Herunterladen</button>
                            <button onclick="printSingleBarcode(${itemId})" class="btn btn-secondary">🖨️ Drucken</button>
                            <button onclick="printCustomLabel(${itemId})" class="btn" style="background: #8b5cf6; color: white;">🎨 Custom Label</button>
                            <button onclick="this.parentElement.parentElement.parentElement.parentElement.remove()" class="btn btn-secondary">Schließen</button>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }
    } catch (error) {
        showAlert('Fehler beim Laden des Barcodes', 'error');
    }
}

function downloadBarcode(itemId) {
    window.location.href = `/api/items/${itemId}/barcode`;
}

function printSingleBarcode(itemId) {
    window.open(`/api/items/barcodes/print?item_id=${itemId}`, '_blank');
}

function printBarcodes() {
    // Hole aktuelle Filter
    const category = document.getElementById('filter-category').value;
    const location = document.getElementById('filter-location').value;

    let url = '/api/items/barcodes/print?';
    if (category) url += `category=${category}&`;
    if (location) url += `location=${location}&`;

    window.open(url, '_blank');
}

async function printCustomLabel(itemId) {
    // Lade verfügbare Templates
    try {
        const result = await apiCall('/api/label-templates');

        if (!result.success || result.templates.length === 0) {
            showAlert('Keine Label-Templates gefunden. Erstelle zuerst ein Template im Label Designer.', 'info');
            return;
        }

        // Erstelle Auswahl-Modal
        const modal = document.createElement('div');
        modal.className = 'modal active';

        let templateOptions = result.templates.map(t =>
            `<div class="template-option" onclick="selectLabelTemplate(${itemId}, ${t.id})" style="padding: 15px; border: 2px solid #e2e8f0; border-radius: 8px; cursor: pointer; margin-bottom: 10px; transition: all 0.2s;">
                <div style="font-weight: 600; font-size: 16px;">${t.name}</div>
                <div style="font-size: 13px; color: #64748b; margin-top: 4px;">${t.width_mm}mm × ${t.height_mm}mm</div>
                ${t.description ? `<div style="font-size: 12px; color: #94a3b8; margin-top: 4px;">${t.description}</div>` : ''}
            </div>`
        ).join('');

        modal.innerHTML = `
            <div class="modal-content" style="max-width: 500px;">
                <div class="modal-header">
                    <h3>Wähle ein Label-Template</h3>
                    <span class="close" onclick="this.parentElement.parentElement.parentElement.remove()">&times;</span>
                </div>
                <div style="padding: 20px; max-height: 400px; overflow-y: auto;">
                    ${templateOptions}
                </div>
                <div style="padding: 20px; border-top: 1px solid #e2e8f0; display: flex; gap: 10px; justify-content: flex-end;">
                    <button onclick="window.open('/label-designer', '_blank')" class="btn" style="background: #8b5cf6; color: white;">+ Neues Template erstellen</button>
                    <button onclick="this.parentElement.parentElement.parentElement.remove()" class="btn btn-secondary">Abbrechen</button>
                </div>
            </div>
        `;

        // Hover-Effekt für Template-Optionen
        modal.querySelectorAll('.template-option').forEach(option => {
            option.addEventListener('mouseenter', () => {
                option.style.borderColor = '#8b5cf6';
                option.style.backgroundColor = '#f5f3ff';
            });
            option.addEventListener('mouseleave', () => {
                option.style.borderColor = '#e2e8f0';
                option.style.backgroundColor = 'transparent';
            });
        });

        document.body.appendChild(modal);
    } catch (error) {
        showAlert('Fehler beim Laden der Templates', 'error');
    }
}

function selectLabelTemplate(itemId, templateId) {
    // Schließe Modal
    document.querySelectorAll('.modal').forEach(m => m.remove());

    // Öffne Print-Seite mit Template
    window.open(`/api/items/print-custom-labels?item_id=${itemId}&template_id=${templateId}`, '_blank');
}

// ============= BARCODE SCANNER =============

async function searchByBarcode() {
    const input = document.getElementById('barcode-scanner-input');
    const resultDiv = document.getElementById('scan-result');
    const barcodeValue = input.value.trim();

    if (!barcodeValue) {
        showAlert('Bitte geben Sie einen Barcode ein', 'error');
        return;
    }

    // Zeige Loading-Zustand
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = '<div class="loading" style="padding: 20px;">Suche Artikel...</div>';

    try {
        // Nutze neue Barcode-Such-API
        const response = await apiCall(`/api/items/search-barcode?barcode=${encodeURIComponent(barcodeValue)}`);
        const item = response.item;

        if (item) {
            // Zeige Artikel-Informationen
            resultDiv.innerHTML = `
                <div style="background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%); padding: 20px; border-radius: 12px; color: white;">
                    <div style="display: flex; justify-content: space-between; align-items: start; gap: 20px;">
                        <div style="flex: 1;">
                            <div style="font-size: 12px; opacity: 0.9; margin-bottom: 8px;">✓ Artikel gefunden</div>
                            <h3 style="font-size: 22px; margin-bottom: 8px; color: white;">${item.name}</h3>
                            ${item.sku ? `<div style="opacity: 0.9; margin-bottom: 4px;">SKU: ${item.sku}</div>` : ''}
                            ${item.barcode ? `<div style="opacity: 0.9; margin-bottom: 4px;">🏷️ ${item.barcode}</div>` : ''}
                            ${item.category_name ? `<div style="opacity: 0.9; margin-bottom: 4px;">📦 ${item.category_name}</div>` : ''}
                            ${item.location_name ? `<div style="opacity: 0.9;">📍 ${item.location_name}</div>` : ''}
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 14px; opacity: 0.9; margin-bottom: 4px;">Bestand</div>
                            <div style="font-size: 32px; font-weight: 700;">${item.quantity}</div>
                            <div style="opacity: 0.9; font-size: 14px;">${item.unit || 'Stück'}</div>
                        </div>
                    </div>
                    <div style="margin-top: 16px; display: flex; gap: 8px; flex-wrap: wrap;">
                        <button onclick="viewItemDetails(${item.id})" class="btn" style="background: white; color: var(--primary); border: none;">
                            📋 Details anzeigen
                        </button>
                        <button onclick="closeScannerAndOpenMovement(${item.id}, 'in')" class="btn btn-success" style="flex: 1;">
                            + Einbuchen
                        </button>
                        <button onclick="closeScannerAndOpenMovement(${item.id}, 'out')" class="btn btn-danger" style="flex: 1;">
                            − Ausbuchen
                        </button>
                    </div>
                </div>
            `;

            // Input leeren für nächsten Scan
            input.value = '';
            input.focus();

        } else {
            resultDiv.innerHTML = `
                <div class="alert alert-error">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="12" y1="8" x2="12" y2="12"/>
                        <line x1="12" y1="16" x2="12.01" y2="16"/>
                    </svg>
                    Artikel nicht gefunden
                </div>
            `;
        }

    } catch (error) {
        // Artikel nicht gefunden - biete Erstellung an
        resultDiv.innerHTML = `
            <div class="alert alert-warning" style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: white; border: none;">
                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="12" y1="8" x2="12" y2="12"/>
                        <line x1="12" y1="16" x2="12.01" y2="16"/>
                    </svg>
                    <div>
                        <div style="font-size: 16px; font-weight: 600;">Artikel nicht gefunden</div>
                        <div style="opacity: 0.9; font-size: 14px; margin-top: 4px;">Barcode: ${barcodeValue}</div>
                    </div>
                </div>
                <button onclick="createItemWithBarcode('${barcodeValue}')" class="btn" style="width: 100%; background: white; color: #d97706; border: none; font-weight: 600;">
                    + Neuen Artikel mit diesem Barcode erstellen
                </button>
            </div>
        `;
    }
}

function createItemWithBarcode(barcode) {
    // Öffne Artikel-Formular und fülle Barcode vor
    openItemForm();

    // Warte bis Formular geladen ist
    setTimeout(() => {
        const barcodeField = document.getElementById('edit-item-barcode');
        if (barcodeField) {
            barcodeField.value = barcode;
            // Fokussiere auf Name-Feld
            document.getElementById('edit-item-name').focus();
        }
    }, 100);
}

function viewItemDetails(itemId) {
    // Schließe Scanner-Modal
    const scannerModal = document.querySelector('.modal.active');
    if (scannerModal) {
        scannerModal.remove();
    }

    // Öffne Bearbeitungs-Modal für den Artikel
    editItem(itemId);
}

function closeScannerAndOpenMovement(itemId, type) {
    // Schließe Scanner-Modal
    const scannerModal = document.querySelector('.modal.active');
    if (scannerModal) {
        scannerModal.remove();
    }

    // Öffne Bewegungs-Modal
    openMovementModal(itemId, type);
}

// Event-Listener für Enter-Taste im Barcode-Feld
document.addEventListener('DOMContentLoaded', function() {
    const barcodeInput = document.getElementById('barcode-scanner-input');
    if (barcodeInput) {
        barcodeInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                searchByBarcode();
            }
        });

        // Auto-Focus bei Seiten-Load
        barcodeInput.focus();
    }
});

function logout() {
    if (confirm('Möchten Sie sich wirklich abmelden?')) {
        window.location.href = '/logout';
    }
}

// ============= BILD-UPLOAD =============

// Bild-Vorschau beim Datei-Auswahl
document.addEventListener('DOMContentLoaded', function() {
    const imageUpload = document.getElementById('item-image-upload');
    if (imageUpload) {
        imageUpload.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const previewDiv = document.getElementById('image-preview');
                    const previewImg = document.getElementById('preview-img');
                    if (previewImg) previewImg.src = e.target.result;
                    if (previewDiv) previewDiv.style.display = 'block';
                };
                reader.readAsDataURL(file);
            }
        });
    }
});

async function uploadItemImage(itemId) {
    const fileInput = document.getElementById('item-image-upload');
    const file = fileInput.files[0];

    if (!file) {
        return; // Kein Bild ausgewählt
    }

    const formData = new FormData();
    formData.append('image', file);

    try {
        const response = await fetch(`/api/items/${itemId}/upload-image`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCSRFToken()
            },
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            showAlert('Bild erfolgreich hochgeladen');
            return result.image_url;
        } else {
            showAlert(result.message || 'Fehler beim Hochladen', 'error');
            return null;
        }
    } catch (error) {
        console.error('Upload-Fehler:', error);
        showAlert('Fehler beim Hochladen des Bildes', 'error');
        return null;
    }
}

async function deleteItemImage() {
    const itemId = document.getElementById('item-id').value;

    if (!itemId || !confirm('Möchten Sie das Bild wirklich löschen?')) {
        return;
    }

    try {
        const response = await apiCall(`/api/items/${itemId}/delete-image`, {
            method: 'DELETE'
        });

        if (response.success) {
            showAlert('Bild erfolgreich gelöscht');

            // UI aktualisieren
            document.getElementById('current-image-container').style.display = 'none';
            document.getElementById('item-image-upload').value = '';
            document.getElementById('image-preview').style.display = 'none';

            // Items neu laden
            await loadItems();
        }
    } catch (error) {
        showAlert('Fehler beim Löschen des Bildes', 'error');
    }
}