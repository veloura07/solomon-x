const { contextBridge, ipcRenderer } = require('electron');

let _authToken = null;

ipcRenderer.on('solomon-auth-token', (_event, token) => {
  _authToken = token;
});

contextBridge.exposeInMainWorld('solomonNative', {
  getAuthToken: () => _authToken,
});
