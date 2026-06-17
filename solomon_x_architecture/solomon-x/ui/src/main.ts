// Solomon X Electron UI Main Process
// Handles window creation, IPC communication with renderer, and system tray

import { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage } from 'electron';
import * as path from 'path';
import * as fs from 'fs';
import { spawn } from 'child_process';

// Global reference to daemon process (for MVP)
let daemonProcess: ChildProcess | null = null;

// Create the browser window
function createWindow() {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      enableRemoteModule: false,
    },
    icon: path.join(__dirname, '../../assets/icon.png'),
    show: false, // Show when ready-to-event is emitted
  });

  // Load the React/Vite app in development, or built files in production
  if (process.env.VITE_DEV_SERVER_URL) {
    win.loadURL(process.env.VITE_DEV_SERVER_URL);
    // Open DevTools in development
    win.webContents.openDevTools();
  } else {
    win.loadFile(path.join(__dirname, '../../dist/index.html'));
  }

  win.once('ready-to-show', () => {
    win.show();
  });

  return win;
}

// Handle IPC messages from renderer
ipcMain.handle('get-version', () => {
  return app.getVersion();
});

ipcMain.handle('send-voice-command', async (event, audioData: ArrayBuffer) => {
  // In production: would send audio to daemon via bus for ASR
  // For MVP: simulate response
  console.log('Received voice command:', audioData.byteLength, 'bytes');

  // Simulate processing delay
  await new Promise(resolve => setTimeout(resolve, 500));

  // Return mock response
  return {
    text: "Hey Solomon, what's 2+2?",
    intent: "query",
    confidence: 0.95
  };
});

ipcMain.handle('get-cognitive-metrics', async () => {
  // In production: would get metrics from cognitive twin via Python bridge
  // For MVP: return mock data
  return {
    focus_index: 0.75,
    cognitive_load: 0.45,
    mental_momentum: 0.2,
    fatigue_level: 0.3,
    recovery_need: 0.6,
    timestamp: Date.now()
  };
});

ipcMain.handle('search-memory', async (event, query: string) => {
  // In production: would send to memory search service via bus
  // For MVP: simulate search
  console.log('Searching memory for:', query);

  await new Promise(resolve => setTimeout(resolve, 200)); // Simulate network delay

  // Return mock results
  return [
    {
      id: "mem_001",
      content: "Rust ownership rules: each value has a single owner at any time",
      timestamp: Date.now() - 3600000, // 1 hour ago
      salience: 0.8,
      novelty: 0.7,
      metadata: { domain: "rust", tags: ["ownership", "basics"] },
      tier: "warm",
      score: 0.85
    },
    {
      id: "mem_002",
      content: "Cognitive load increases during task switching",
      timestamp: Date.now() - 7200000, // 2 hours ago
      salience: 0.7,
      novelty: 0.6,
      metadata: { domain": "psychology", tags: ["cognitive", "productivity"] },
      tier": "hot",
      score: 0.75
    }
  ];
});

// Handle application lifecycle
app.whenReady().then(() => {
  // Start the Rust daemon (in production)
  // For MVP: we'll skip this and assume it's running separately
  console.log('Starting Solomon X UI...');

  // Create main window
  const mainWindow = createWindow();

  // Create system tray
  const iconPath = path.join(__dirname, '../../assets/icon.png');
  const trayIcon = nativeImage.createFromPath(iconPath);
  const tray = new Tray(trayIcon.resize({ width: 16, height: 16 }));

  const contextMenu = Menu.buildFromTemplate([
    { label: 'Show Solomon', click: () => mainWindow.show() },
    { label: 'Hide Solomon', click: () => mainWindow.hide() },
    { type: 'separator' },
    { label: 'Quit', click: () => app.quit() }
  ]);

  tray.setToolTip('Solomon X - Your Cognitive Companion');
  tray.setContextMenu(contextMenu);

  // Open devtools if in development
  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.webContents.openDevTools();
  }
});

// Quit when all windows are closed (except on macOS)
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  // On macOS, re-create window when dock icon is clicked and no other windows open
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// Handle graceful shutdown
app.on('before-quit', () => {
  console.log('Shutting down Solomon X...');
  // In production: would signal daemon to shutdown gracefully
  if (daemonProcess) {
    daemonProcess.kill();
  }
});