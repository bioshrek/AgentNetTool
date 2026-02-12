import {
  app,
  BrowserWindow,
  screen,
  dialog,
  ipcMain,
  globalShortcut,
  shell,
  Notification,
  protocol,
  Menu,
  nativeImage,
  Tray,
} from "electron";
import { spawn, ChildProcess, execSync } from "child_process";
import axios from "axios";
import path from "path";
import fs from "fs";
import { SERVER_URL } from "./public/constant";
import { createTray, StartRecording, StopRecording, updateTrayIcon } from "./trayicon";

const log = require("electron-log");

// Log user data path for debugging storage location
log.info(`Electron userData path: ${app.getPath('userData')}`);

declare const MAIN_WINDOW_WEBPACK_ENTRY: string;
declare const MAIN_WINDOW_PRELOAD_WEBPACK_ENTRY: string;

ipcMain.handle("dialog:openDirectory", async (event, options = {}) => {
  if (!mainWindow) return undefined;

  // Use mainWindow as parent to ensure dialog stays in front (modal)
  // This resolves the z-order/visibility issue
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ["openDirectory"],
    ...options
  });
  
  if (result.canceled) {
    return undefined;
  }
  return result.filePaths[0];
});

// Folder storage handlers
const FOLDER_DATA_FILE = path.join(app.getPath('home'), '.config', 'vis', 'folder-structure.json');

ipcMain.handle("folder:save", async (event, data) => {
  try {
    const folderDir = path.dirname(FOLDER_DATA_FILE);
    if (!fs.existsSync(folderDir)) {
      fs.mkdirSync(folderDir, { recursive: true });
    }
    fs.writeFileSync(FOLDER_DATA_FILE, JSON.stringify(data, null, 2), 'utf-8');
    log.info(`Folder data saved to: ${FOLDER_DATA_FILE}`);
    return { success: true };
  } catch (error) {
    log.error('Error saving folder data:', error);
    return { success: false, error: error.message };
  }
});

ipcMain.handle("folder:load", async () => {
  try {
    if (fs.existsSync(FOLDER_DATA_FILE)) {
      const data = fs.readFileSync(FOLDER_DATA_FILE, 'utf-8');
      log.info(`Folder data loaded from: ${FOLDER_DATA_FILE}`);
      return JSON.parse(data);
    }
    return null;
  } catch (error) {
    log.error('Error loading folder data:', error);
    return null;
  }
});

let tray: Tray | null = null;
if (require("electron-squirrel-startup")) {
  app.quit();
}


let mainWindow: BrowserWindow | null = null;
let flaskProcess: ChildProcess | null = null;

const createWindow = (): void => {
  log.info("Creating main window...");
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;

  mainWindow = new BrowserWindow({
    width,
    height,
    webPreferences: {
      preload: MAIN_WINDOW_PRELOAD_WEBPACK_ENTRY,
      webSecurity: false,
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadURL(MAIN_WINDOW_WEBPACK_ENTRY);
  log.info(`Loading URL: ${MAIN_WINDOW_WEBPACK_ENTRY}`);

  // if (process.env.NODE_ENV === "development") {
  //   mainWindow.webContents.openDevTools();
  // }
  
  mainWindow.once('ready-to-show', () => {
    log.info("Main window ready to show");
    mainWindow?.show();
  });

  mainWindow.on("closed", () => {
    log.info("Main window closed");
    mainWindow = null;
  });
};

const startFlaskServer = (): void => {
  if (app.isPackaged) {
    const backendPath = path.join(process.resourcesPath, "backend/backend");
    log.info(`Attempting to spawn backend at: ${backendPath}`);
    
    try {
      if (fs.existsSync(backendPath)) {
        log.info("Backend file exists.");
        const stats = fs.statSync(backendPath);
        log.info(`File permissions: ${stats.mode.toString(8)}`);
      } else {
        log.error("Backend file DOES NOT exist.");
        // List resources contents
        try {
          const resources = fs.readdirSync(process.resourcesPath);
          log.info(`Contents of resources: ${resources.join(", ")}`);
          const backendDir = path.join(process.resourcesPath, "backend");
          if (fs.existsSync(backendDir)) {
             const backendContents = fs.readdirSync(backendDir);
             log.info(`Contents of resources/backend: ${backendContents.join(", ")}`);
          }
        } catch (e) {
          log.error(`Error listing directories: ${e}`);
        }
      }
    } catch (e) {
      log.error(`Error checking file: ${e}`);
    }

    // Check if file exists and invoke it
    flaskProcess = spawn(backendPath, {
      env: { ...process.env },
      shell: false,
    });
  } else {
    flaskProcess = spawn("uv", ["run", "python", "api/backend.py"], {
      env: { ...process.env, FLASK_DEBUG: "1" },
      shell: true,
    });
  }

  flaskProcess.stdout.on("data", (data) => {
    console.log(`Flask stdout: ${data}`);
    log.info(`Flask stdout: ${data}`);
  });

  flaskProcess.stderr.on("data", (data) => {
    console.error(`Flask stderr: ${data}`);
    log.error(`Flask stderr: ${data}`);
  });

  flaskProcess.on("close", (code) => {
    console.log(`Flask process exited with code ${code}`);
    log.info(`Flask process exited with code ${code}`);
  });
  
  flaskProcess.on("error", (err) => {
    console.error(`Flask process spawn error: ${err}`);
    log.error(`Flask process spawn error: ${err}`);
  });
};

const stopFlaskServer = (): void => {
  if (flaskProcess) {
    flaskProcess.kill();
    flaskProcess = null;
  }
};

const checkFlaskServer = async (): Promise<void> => {
  try {
    await axios.get("http://localhost:5328/api/recordings");
    if (process.platform === "darwin") {
      await axios.get("http://localhost:5328/api/check_permissions");
    }
    createWindow();
  } catch (error) {
    console.log("Waiting for Flask server to start...");
    setTimeout(checkFlaskServer, 1000);
  }
};

app.on("ready", () => {
  startFlaskServer();
  log.info("Flask server started");
  checkFlaskServer();
  log.info("Checked Flask server");

  ipcMain.on("start-record-icon", () => {
    StartRecording();
    tray?.setTitle("Recording...");
  });
  ipcMain.on("stop-record-icon", () => {
    StopRecording();
    tray?.setTitle("AgentNet");
  });

  ipcMain.on("tree-start", () => {
    updateTrayIcon("red");
    tray?.setTitle("Please Don't move....");
  });

  ipcMain.on("tree-end", () => {
    updateTrayIcon("green");
    tray?.setTitle("Recording...");
  });

  globalShortcut.register("CommandOrControl+Alt+R", () => {
    mainWindow?.webContents.send("start-record");
  });

  globalShortcut.register("CommandOrControl+Alt+T", () => {
    mainWindow?.webContents.send("stop-record");
  });

  // TODO: Add global shortcuts for AXTree: CommandOrControl+Shift+T
  globalShortcut.register("CommandOrControl+Shift+T", () => {
    mainWindow?.webContents.send("get-axtree");
  });

  ipcMain.on("minimize-window", () => {
    if (mainWindow) {
      mainWindow.minimize();
    }
  });

  ipcMain.on("maximize-window", () => {
    if (mainWindow) {
      if (mainWindow.isMaximized()) {
        mainWindow.unmaximize();
      } else {
        mainWindow.maximize();
      }
    }
  });

  ipcMain.on("get_os_system", () => {
    log.info("Received get_os_system request");
    mainWindow?.webContents.send("get_os_system_response", process.platform);
  });
});

app.whenReady().then(() => {
  tray = createTray(app);
});

const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  app.quit();
} else {
  app.on("second-instance", (event, commandLine, workingDirectory) => {
    // Someone tried to run a second instance, we should focus our window.
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
    const url = commandLine.pop();
    console.log(`You arrived from ${url}`);
  });
}


app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("will-quit", async () => {
  if (process.platform === "win32") {
    await kill_process(5328);
  }
  stopFlaskServer();
  globalShortcut.unregisterAll();
});

function kill_process(port: number): Promise<void> {
  return new Promise((resolve, reject) => {
    console.log(`Checking for processes using port ${port}...`);

    try {
      const stdout = execSync("netstat -ano").toString();
      const lines = stdout.split("\n");
      const pids = new Set<number>();

      for (const line of lines) {
        if (line.includes(`:${port}`)) {
          const parts = line.trim().split(/\s+/);
          const pid = parseInt(parts[parts.length - 1], 10);
          if (!isNaN(pid) && pid !== 0) {
            pids.add(pid);
          }
        }
      }

      if (pids.size === 0) {
        console.log(`No processes found using port ${port}.`);
        resolve();
        return;
      }

      pids.forEach((pid) => {
        console.log(`Killing process with PID ${pid} using port ${port}.`);
        try {
          execSync(`taskkill /F /PID ${pid}`);
          console.log(`Successfully killed process with PID ${pid}.`);
        } catch (error) {
          console.error(`Failed to kill process with PID ${pid}: ${error}`);
        }
      });

      resolve();
    } catch (error) {
      console.error(`Failed to run netstat command: ${error}`);
      reject(error);
    }
  });
}
