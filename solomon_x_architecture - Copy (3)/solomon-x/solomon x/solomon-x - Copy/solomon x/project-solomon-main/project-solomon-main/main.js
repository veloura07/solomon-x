const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const crypto = require('crypto');

// Disable GPU to avoid crashes on systems without proper drivers
app.disableHardwareAcceleration();
app.commandLine.appendSwitch('disable-gpu');
app.commandLine.appendSwitch('disable-software-rasterizer');

// ── Brain process (local Python) ───────────────────────────────────────────
// Launch brain.py from the local project directory using the system Python.
let brainProcess = null;
let authToken = null;

function startBrain() {
    const pythonCmd = process.env.PYTHON || process.env.PYTHON3 || 'python';
    const brainScriptPath = path.join(__dirname, 'brain.py');

    // Ensure an auth token exists for this Electron session
    if (!authToken) {
        authToken = crypto.randomBytes(32).toString('hex');
    }

    brainProcess = spawn(pythonCmd, [brainScriptPath], {
        stdio: ['ignore', 'pipe', 'pipe'],
        env: Object.assign({}, process.env, { SOLOMON_AUTH_TOKEN: authToken }),
    });

    // Forward brain.py stdout to Electron's console (visible in DevTools)
    brainProcess.stdout.on('data', (data) => {
        process.stdout.write(`[brain] ${data}`);
    });

    // Forward brain.py stderr separately so errors are easy to spot
    brainProcess.stderr.on('data', (data) => {
        process.stderr.write(`[brain:err] ${data}`);
    });

    brainProcess.on('exit', (code, signal) => {
        if (code !== null) {
            console.log(`[brain] Process exited with code ${code}`);
        } else if (signal !== null) {
            console.log(`[brain] Process killed by signal ${signal}`);
        }
        brainProcess = null;
    });

    brainProcess.on('error', (err) => {
        console.error(`[brain] Failed to start local Python process: ${err.message}`);
        console.error('[brain] Ensure Python is installed and available on PATH, and that brain.py exists in the project root.');
    });

    console.log('[brain] Spawned brain.py via local Python.');
}

function stopBrain() {
    if (brainProcess) {
        console.log('[brain] Shutting down brain process...');
        brainProcess.kill();
        brainProcess = null;
    }
}


// ── Electron window ───────────────────────────────────────────────────────────

function createWindow() {
    const win = new BrowserWindow({
        width: 1440,
        height: 900,
        frame: false,
        backgroundColor: '#02010a',
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js'),
        }
    });

    win.loadFile(path.join(__dirname, 'ui', 'index.html'));

    // Send the ephemeral auth token to the renderer once the page has loaded
    win.webContents.once('did-finish-load', () => {
        try {
            if (authToken) {
                win.webContents.send('solomon-auth-token', authToken);
            }
        } catch (err) {
            console.error('[main] Failed to send auth token to renderer:', err);
        }
    });
}


// ── App lifecycle ─────────────────────────────────────────────────────────────

app.whenReady().then(() => {
    startBrain();    // Start Python backend first
    setTimeout(createWindow, 1500);  // Give brain.py time to bind ws port
});

app.on('window-all-closed', () => {
    stopBrain();     // Kill brain.py before quitting
    app.quit();
});

// Safety net: also kill brain if Electron is force-quit
process.on('exit', stopBrain);
process.on('SIGTERM', () => { stopBrain(); process.exit(0); });