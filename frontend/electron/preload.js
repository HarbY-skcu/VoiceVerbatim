const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("api", {
  // Expanded in future tickets as IPC channels are needed
});
