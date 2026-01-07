// ============= BACKUP MANAGER =============

async function showBackupManager() {
    try {
        const result = await apiCall('/api/backup/list');

        if (!result.success) {
            showAlert('Fehler beim Laden der Backups: ' + result.error, 'error');
            return;
        }

        const backups = result.backups || [];

        const modal = document.createElement('div');
        modal.className = 'modal active';
        modal.innerHTML = `
            <div class="modal-content" style="max-width: 900px;">
                <div class="modal-header">
                    <h3>📦 Backup-Verwaltung</h3>
                    <span class="close" onclick="this.parentElement.parentElement.parentElement.remove()">&times;</span>
                </div>
                <div class="modal-body">
                    ${backups.length === 0 ? `
                        <div style="text-align: center; padding: 40px; color: var(--text-secondary);">
                            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" style="margin-bottom: 20px; opacity: 0.5;">
                                <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/>
                            </svg>
                            <p>Keine Backups gefunden</p>
                            <p style="font-size: 14px;">Erstelle dein erstes Backup über das Menü</p>
                        </div>
                    ` : `
                        <div style="margin-bottom: 20px;">
                            <p style="color: var(--text-secondary); font-size: 14px;">
                                <strong>${backups.length}</strong> Backup(s) verfügbar auf Google Drive
                            </p>
                        </div>
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Datum</th>
                                    <th>Name</th>
                                    <th>Größe</th>
                                    <th>Aktionen</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${backups.map(backup => `
                                    <tr>
                                        <td>${formatBackupDate(backup.createdTime)}</td>
                                        <td style="font-family: monospace; font-size: 13px;">${backup.name}</td>
                                        <td>${formatFileSize(backup.size)}</td>
                                        <td>
                                            <button onclick="downloadBackupFile('${backup.id}', '${backup.name}')" class="btn btn-sm btn-secondary" title="Herunterladen">
                                                ⬇️
                                            </button>
                                            <button onclick="restoreBackupConfirm('${backup.id}', '${backup.name}')" class="btn btn-sm btn-primary" title="Wiederherstellen">
                                                ♻️
                                            </button>
                                            <button onclick="window.open('${backup.webViewLink}', '_blank')" class="btn btn-sm" style="background: #4285f4; color: white;" title="In Google Drive öffnen">
                                                🔗
                                            </button>
                                        </td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    `}
                </div>
                <div class="modal-footer">
                    <button onclick="syncToCloud().then(() => showBackupManager())" class="btn btn-primary">
                        🔄 Neues Backup erstellen
                    </button>
                    <button onclick="this.parentElement.parentElement.parentElement.remove()" class="btn btn-secondary">
                        Schließen
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

    } catch (error) {
        showAlert('Fehler beim Laden der Backups: ' + error.message, 'error');
    }
}

function formatBackupDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('de-DE', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function formatFileSize(bytes) {
    if (!bytes) return 'N/A';
    const mb = bytes / (1024 * 1024);
    return mb.toFixed(2) + ' MB';
}

async function downloadBackupFile(fileId, filename) {
    try {
        showAlert('Backup wird heruntergeladen...', 'info');
        window.location.href = `/api/backup/download/${fileId}`;
    } catch (error) {
        showAlert('Fehler beim Herunterladen: ' + error.message, 'error');
    }
}

function restoreBackupConfirm(fileId, filename) {
    if (!confirm(`⚠️ WARNUNG!\n\nMöchten Sie wirklich dieses Backup wiederherstellen?\n\n"${filename}"\n\nDie aktuelle Datenbank wird überschrieben!\n(Ein Sicherungs-Backup wird automatisch erstellt)`)) {
        return;
    }

    if (!confirm(`Sind Sie ABSOLUT SICHER?\n\nAlle aktuellen Daten werden ersetzt!`)) {
        return;
    }

    restoreBackup(fileId, filename);
}

async function restoreBackup(fileId, filename) {
    try {
        showAlert('Backup wird wiederhergestellt...', 'info');

        const result = await apiCall(`/api/backup/restore/${fileId}`, {
            method: 'POST'
        });

        if (result.success) {
            showAlert('✓ Backup erfolgreich wiederhergestellt!\n\nDie Seite wird neu geladen...', 'success');

            // Schließe alle Modals
            document.querySelectorAll('.modal').forEach(m => m.remove());

            // Lade Seite neu nach 2 Sekunden
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } else {
            showAlert('Fehler beim Wiederherstellen: ' + result.error, 'error');
        }

    } catch (error) {
        showAlert('Fehler beim Wiederherstellen: ' + error.message, 'error');
    }
}
