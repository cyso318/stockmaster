/**
 * Barcode-Scanner mit QuaggaJS
 * Echtes Barcode-Decoding für EAN, Code128, Code39, etc.
 */

let quaggaActive = false;
let lastDetectedCode = null;
let lastDetectionTime = 0;
const DETECTION_COOLDOWN = 2000; // 2 Sekunden

/**
 * Öffnet Kamera-Scanner mit QuaggaJS
 */
async function openCameraScanner() {
    console.log('openCameraScanner() aufgerufen');

    // Prüfe ob Browser Kamera unterstützt
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        showAlert('Kamera wird von Ihrem Browser nicht unterstützt', 'error');
        return;
    }

    // Prüfe ob QuaggaJS geladen ist
    if (typeof Quagga === 'undefined') {
        console.error('QuaggaJS nicht geladen');
        showAlert('Barcode-Scanner-Bibliothek wird geladen... Bitte erneut versuchen.', 'error');
        return;
    }

    console.log('✓ Browser und QuaggaJS OK')

    // Modal erstellen
    const modal = document.createElement('div');
    modal.className = 'modal active';
    modal.id = 'camera-scanner-modal';
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 600px; height: 90vh; display: flex; flex-direction: column; padding: 0;">
            <div class="modal-header" style="border-radius: 16px 16px 0 0;">
                <h3>📷 Barcode scannen</h3>
                <span class="close" onclick="closeCameraScanner()">&times;</span>
            </div>

            <div style="flex: 1; position: relative; background: #000; border-radius: 0 0 16px 16px; overflow: hidden;">
                <!-- Quagga Video Container -->
                <div id="quagga-scanner" style="width: 100%; height: 100%; position: relative;">
                    <video style="width: 100%; height: 100%; object-fit: cover;"></video>
                    <canvas class="drawingBuffer" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"></canvas>
                </div>

                <!-- Scan-Overlay -->
                <div style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; pointer-events: none;">
                    <!-- Scan-Rahmen -->
                    <div style="
                        position: absolute;
                        top: 50%;
                        left: 50%;
                        transform: translate(-50%, -50%);
                        width: 80%;
                        max-width: 400px;
                        height: 200px;
                        border: 2px solid #6366f1;
                        border-radius: 12px;
                        box-shadow: 0 0 0 2000px rgba(0,0,0,0.5);
                    ">
                        <!-- Ecken -->
                        <div style="position: absolute; top: -2px; left: -2px; width: 30px; height: 30px; border-top: 4px solid #fff; border-left: 4px solid #fff; border-radius: 4px 0 0 0;"></div>
                        <div style="position: absolute; top: -2px; right: -2px; width: 30px; height: 30px; border-top: 4px solid #fff; border-right: 4px solid #fff; border-radius: 0 4px 0 0;"></div>
                        <div style="position: absolute; bottom: -2px; left: -2px; width: 30px; height: 30px; border-bottom: 4px solid #fff; border-left: 4px solid #fff; border-radius: 0 0 0 4px;"></div>
                        <div style="position: absolute; bottom: -2px; right: -2px; width: 30px; height: 30px; border-bottom: 4px solid #fff; border-right: 4px solid #fff; border-radius: 0 0 4px 0;"></div>

                        <!-- Scan-Linie -->
                        <div style="
                            position: absolute;
                            top: 50%;
                            left: 0;
                            right: 0;
                            height: 2px;
                            background: linear-gradient(90deg, transparent, #6366f1, #ec4899, transparent);
                            transform: translateY(-50%);
                            box-shadow: 0 0 10px #6366f1;
                            animation: scanLine 2s ease-in-out infinite;
                        "></div>
                    </div>

                    <!-- Status Text -->
                    <div id="scan-status" style="
                        position: absolute;
                        top: 20px;
                        left: 0;
                        right: 0;
                        text-align: center;
                        color: white;
                        font-size: 14px;
                        font-weight: 600;
                        text-shadow: 0 2px 4px rgba(0,0,0,0.8);
                        padding: 8px 20px;
                        background: rgba(0,0,0,0.5);
                        backdrop-filter: blur(10px);
                        border-radius: 20px;
                        margin: 0 20px;
                        display: inline-block;
                        left: 50%;
                        transform: translateX(-50%);
                    ">
                        📸 Halten Sie den Barcode in den Rahmen
                    </div>
                </div>

                <!-- Buttons -->
                <div style="position: absolute; bottom: 20px; left: 0; right: 0; display: flex; justify-content: center; gap: 12px; padding: 0 20px;">
                    <button onclick="switchQuaggaCamera()" class="btn btn-secondary" style="flex: 1; max-width: 140px;">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                            <circle cx="12" cy="12" r="3"/>
                        </svg>
                        Wechseln
                    </button>
                    <button onclick="toggleFlashlight()" class="btn btn-secondary" style="flex: 1; max-width: 140px;" id="flashlight-btn">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                        </svg>
                        Licht
                    </button>
                </div>
            </div>
        </div>

        <style>
            @keyframes scanLine {
                0%, 100% { top: 30%; }
                50% { top: 70%; }
            }

            #camera-scanner-modal .modal-content {
                padding: 0 !important;
            }

            #quagga-scanner canvas.drawingBuffer {
                opacity: 0.7;
            }

            @media (max-width: 768px) {
                #camera-scanner-modal .modal-content {
                    max-width: 100%;
                    width: 100%;
                    height: 100vh;
                    max-height: 100vh;
                    border-radius: 0;
                }

                #camera-scanner-modal .modal-header {
                    border-radius: 0;
                }

                #camera-scanner-modal .modal-content > div:last-child {
                    border-radius: 0;
                }
            }
        </style>
    `;

    document.body.appendChild(modal);

    // Quagga initialisieren
    try {
        await initQuagga();
    } catch (error) {
        console.error('Quagga-Fehler:', error);
        showAlert('Kamera konnte nicht gestartet werden: ' + error.message, 'error');
        modal.remove();
    }
}

/**
 * Initialisiert QuaggaJS
 */
function initQuagga() {
    return new Promise((resolve, reject) => {
        Quagga.init({
            inputStream: {
                name: "Live",
                type: "LiveStream",
                target: document.querySelector('#quagga-scanner'),
                constraints: {
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                    facingMode: "environment", // Rückkamera
                    aspectRatio: { ideal: 16/9 }
                },
                area: { // Scan-Bereich (mittlere 60%)
                    top: "20%",
                    right: "10%",
                    left: "10%",
                    bottom: "20%"
                }
            },
            locator: {
                patchSize: "medium",
                halfSample: true
            },
            numOfWorkers: navigator.hardwareConcurrency || 4,
            decoder: {
                readers: [
                    "ean_reader",        // EAN-13, EAN-8
                    "ean_8_reader",
                    "code_128_reader",   // Code 128
                    "code_39_reader",    // Code 39
                    "code_39_vin_reader",
                    "codabar_reader",
                    "upc_reader",        // UPC
                    "upc_e_reader",
                    "i2of5_reader"       // Interleaved 2 of 5
                ],
                multiple: false
            },
            locate: true,
            frequency: 10 // Scans pro Sekunde
        }, (err) => {
            if (err) {
                console.error('Quagga Init Fehler:', err);
                reject(err);
                return;
            }

            console.log("✓ Quagga erfolgreich initialisiert");

            // Barcode-Detection-Handler
            Quagga.onDetected((result) => {
                const code = result.codeResult.code;
                const now = Date.now();

                // Prüfe Cooldown
                if (code === lastDetectedCode && (now - lastDetectionTime) < DETECTION_COOLDOWN) {
                    return;
                }

                lastDetectedCode = code;
                lastDetectionTime = now;

                console.log("✓ Barcode erkannt:", code);

                // Update UI
                const statusDiv = document.getElementById('scan-status');
                if (statusDiv) {
                    statusDiv.innerHTML = `✓ Erkannt: <strong>${code}</strong>`;
                    statusDiv.style.background = 'rgba(34, 197, 94, 0.9)';
                }

                // Vibriere
                if ('vibrate' in navigator) {
                    navigator.vibrate([200, 100, 200]);
                }

                // Audio-Feedback (optional)
                playBeepSound();

                // Nach 500ms: Scanner schließen und Artikel suchen
                setTimeout(() => {
                    closeCameraScanner();
                    document.getElementById('barcode-scanner-input').value = code;
                    searchByBarcode();
                }, 500);
            });

            // Processing-Handler (für Debugging)
            Quagga.onProcessed((result) => {
                const drawingCtx = Quagga.canvas.ctx.overlay;
                const drawingCanvas = Quagga.canvas.dom.overlay;

                if (result) {
                    // Zeichne Erkennungsbox
                    if (result.boxes) {
                        drawingCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);

                        result.boxes.filter(box => box !== result.box).forEach(box => {
                            Quagga.ImageDebug.drawPath(box, {x: 0, y: 1}, drawingCtx, {
                                color: "rgba(99, 102, 241, 0.5)",
                                lineWidth: 2
                            });
                        });
                    }

                    // Zeichne gefundene Box
                    if (result.box) {
                        Quagga.ImageDebug.drawPath(result.box, {x: 0, y: 1}, drawingCtx, {
                            color: "rgba(34, 197, 94, 0.8)",
                            lineWidth: 3
                        });
                    }

                    // Zeichne Barcode-Linie
                    if (result.codeResult && result.codeResult.code) {
                        Quagga.ImageDebug.drawPath(result.line, {x: 'x', y: 'y'}, drawingCtx, {
                            color: 'rgba(236, 72, 153, 0.8)',
                            lineWidth: 3
                        });
                    }
                }
            });

            // Starte Quagga
            Quagga.start();
            quaggaActive = true;
            resolve();
        });
    });
}

/**
 * Schließt Kamera-Scanner
 */
function closeCameraScanner() {
    if (quaggaActive) {
        Quagga.stop();
        quaggaActive = false;
    }

    lastDetectedCode = null;
    lastDetectionTime = 0;

    const modal = document.getElementById('camera-scanner-modal');
    if (modal) {
        modal.remove();
    }
}

/**
 * Wechselt Kamera (Front/Rück)
 */
async function switchQuaggaCamera() {
    if (!quaggaActive) return;

    try {
        Quagga.stop();

        // Toggle facingMode
        const currentStream = Quagga.CameraAccess.getActiveStreamLabel();
        const newFacingMode = currentStream.includes('back') ? 'user' : 'environment';

        // Neu initialisieren mit anderer Kamera
        await initQuagga();

    } catch (error) {
        console.error('Fehler beim Kamera-Wechsel:', error);
        showAlert('Kamera konnte nicht gewechselt werden', 'error');
    }
}

/**
 * Schaltet Taschenlampe ein/aus (falls unterstützt)
 */
async function toggleFlashlight() {
    try {
        const track = Quagga.CameraAccess.getActiveTrack();

        if (!track) {
            showAlert('Keine aktive Kamera gefunden', 'error');
            return;
        }

        const capabilities = track.getCapabilities();

        if (!capabilities.torch) {
            showAlert('Taschenlampe wird nicht unterstützt', 'error');
            return;
        }

        const settings = track.getSettings();
        const newTorchState = !settings.torch;

        await track.applyConstraints({
            advanced: [{ torch: newTorchState }]
        });

        // Update Button
        const btn = document.getElementById('flashlight-btn');
        if (btn) {
            btn.style.background = newTorchState ? '#6366f1' : '';
            btn.style.color = newTorchState ? 'white' : '';
        }

    } catch (error) {
        console.error('Taschenlampen-Fehler:', error);
        showAlert('Taschenlampe konnte nicht aktiviert werden', 'error');
    }
}

/**
 * Spielt Beep-Sound ab
 */
function playBeepSound() {
    try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);

        oscillator.frequency.value = 800;
        oscillator.type = 'sine';

        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.1);

        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.1);
    } catch (error) {
        // Audio nicht verfügbar - ignorieren
    }
}

// Cleanup beim Verlassen der Seite
window.addEventListener('beforeunload', () => {
    if (quaggaActive) {
        Quagga.stop();
    }
});
