import { app, Menu, nativeImage, Tray, BrowserWindow, shell, ipcMain } from "electron";
import { menubar, Menubar } from "menubar";
import * as path from "path";
import { PythonProcess } from "./python-process";
import { SettingsManager, Settings } from "./settings";
import { HistoryManager, TranscriptFile } from "./history";

// Paths (computed lazily after app ready)
function getAppSupportDir(): string {
  return path.join(app.getPath("appData"), "OhhBrother");
}
function getTranscriptsDir(): string {
  return path.join(getAppSupportDir(), "transcripts");
}
function getConfigPath(): string {
  return path.join(getAppSupportDir(), "config.json");
}

// Find Python in the app bundle or development location
function getPythonDir(): string {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "python");
  }
  // In dev mode, use cwd (electron . is run from project root)
  return path.join(process.cwd(), "python");
}

class OhhBrotherApp {
  private mb: Menubar | null = null;
  private tray: Tray | null = null;
  private pythonProcess!: PythonProcess;
  private settings!: SettingsManager;
  private history!: HistoryManager;
  private isRecording = false;
  private recordingDuration = 0;
  private currentSession: string | null = null;

  private init(): void {
    this.pythonProcess = new PythonProcess(getPythonDir(), getTranscriptsDir());
    this.settings = new SettingsManager(getConfigPath());
    this.history = new HistoryManager(getTranscriptsDir());

    this.setupPythonCallbacks();
    this.setupIPC();
  }

  private setupIPC(): void {
    ipcMain.handle("get-settings", () => {
      return this.settings.get();
    });

    ipcMain.handle("save-settings", (_event, newSettings: Settings) => {
      this.settings.set(newSettings);
      return true;
    });
  }

  private setupPythonCallbacks(): void {
    this.pythonProcess.onMessage((msg) => {
      switch (msg.type) {
        case "ready":
          console.log("Python process ready");
          break;
        case "status":
          this.isRecording = msg.recording;
          this.recordingDuration = msg.duration || 0;
          this.updateMenu();
          break;
        case "started":
          this.isRecording = true;
          this.currentSession = msg.session;
          this.updateMenu();
          break;
        case "stopped":
          this.isRecording = false;
          this.currentSession = null;
          this.recordingDuration = 0;
          this.updateMenu();
          break;
        case "transcript":
          // Could display in a window if desired
          console.log(msg.text);
          break;
        case "error":
          console.error("Python error:", msg.message);
          break;
        case "saved":
          console.log("Transcript saved:", msg.path);
          this.updateMenu();
          break;
      }
    });

    this.pythonProcess.onError((error) => {
      console.error("Python process error:", error);
    });
  }

  private getIcon(recording: boolean): string {
    // Use simple template images for menu bar
    // In production, these would be actual icon files
    const iconName = recording ? "icon-recording.png" : "icon.png";
    if (app.isPackaged) {
      return path.join(process.resourcesPath, "assets", iconName);
    }
    return path.join(process.cwd(), "assets", iconName);
  }

  private formatDuration(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  }

  private buildMenu(): Menu {
    const historyFiles = this.history.getRecentFiles(10);

    const template: Electron.MenuItemConstructorOptions[] = [
      // Recording status
      this.isRecording
        ? {
            label: `● Recording... (${this.formatDuration(this.recordingDuration)})`,
            enabled: false,
          }
        : {
            label: "Start Recording",
            click: () => this.startRecording(),
          },

      // Stop button (only when recording)
      ...(this.isRecording
        ? [
            {
              label: "Stop Recording",
              click: () => this.stopRecording(),
            },
          ]
        : []),

      { type: "separator" as const },

      // Summarize
      {
        label: "Summarize Current",
        enabled: this.isRecording || historyFiles.length > 0,
        click: () => this.summarizeTranscript(),
      },

      { type: "separator" as const },

      // History items inline
      ...(historyFiles.length > 0
        ? historyFiles.map((file) => ({
            label: file.displayName,
            click: () => this.openTranscript(file),
          }))
        : [{ label: "No transcripts yet", enabled: false }]),

      { type: "separator" as const },

      // Open folder
      {
        label: "Open Transcripts Folder",
        click: () => this.openTranscriptsFolder(),
      },

      // Settings
      {
        label: "Settings...",
        click: () => this.openSettings(),
      },

      // Quit
      {
        label: "Quit",
        click: () => this.quit(),
      },
    ];

    return Menu.buildFromTemplate(template);
  }

  private updateMenu(): void {
    if (this.tray) {
      this.tray.setContextMenu(this.buildMenu());
      // Update icon based on recording state
      try {
        const iconPath = this.getIcon(this.isRecording);
        const icon = nativeImage.createFromPath(iconPath);
        if (!icon.isEmpty()) {
          this.tray.setImage(icon);
        }
      } catch (e) {
        // Icon files may not exist yet
      }
    }
  }

  private async startRecording(): Promise<void> {
    if (this.isRecording) return;
    await this.pythonProcess.start();
    this.pythonProcess.send({ command: "start" });
  }

  private stopRecording(): void {
    if (!this.isRecording) return;
    this.pythonProcess.send({ command: "stop" });
  }

  private openTranscript(file: TranscriptFile): void {
    shell.openPath(file.path);
  }

  private deleteOldTranscripts(daysOld: number): void {
    this.history.deleteOlderThan(daysOld);
    this.updateMenu();
  }

  private openTranscriptsFolder(): void {
    shell.openPath(getTranscriptsDir());
  }

  private openSettings(): void {
    // Create a simple settings window
    const win = new BrowserWindow({
      width: 500,
      height: 400,
      title: "Ohh Brother Settings",
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        preload: path.join(process.cwd(), "dist", "electron", "preload.js"),
      },
    });

    // Load settings HTML
    win.loadFile(path.join(process.cwd(), "dist", "renderer", "settings.html"));
  }

  private async summarizeTranscript(): Promise<void> {
    // Get the most recent transcript
    const files = this.history.getRecentFiles(1);
    if (files.length === 0) return;

    const transcript = this.history.readTranscript(files[0].path);
    if (!transcript) return;

    const settings = this.settings.get();
    if (!settings.llm?.apiKey) {
      console.log("No API key configured for summarization");
      return;
    }

    // Create summary window
    const win = new BrowserWindow({
      width: 600,
      height: 500,
      title: "Meeting Summary",
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        preload: path.join(process.cwd(), "dist", "electron", "preload.js"),
      },
    });

    win.loadFile(path.join(process.cwd(), "dist", "renderer", "summary.html"));

    // Send transcript to renderer for summarization
    win.webContents.on("did-finish-load", () => {
      win.webContents.send("summarize", {
        transcript,
        settings: settings.llm,
      });
    });
  }

  private quit(): void {
    this.stopRecording();
    this.pythonProcess.stop();
    app.quit();
  }

  async start(): Promise<void> {
    await app.whenReady();

    // Initialize after app is ready (paths need app.getPath)
    this.init();

    // Hide dock icon (menu bar app)
    app.dock?.hide();

    // Create tray
    const iconPath = this.getIcon(false);
    let icon: nativeImage;
    try {
      icon = nativeImage.createFromPath(iconPath);
      if (icon.isEmpty()) {
        // Create a simple placeholder icon
        icon = nativeImage.createEmpty();
      }
    } catch {
      icon = nativeImage.createEmpty();
    }

    this.tray = new Tray(icon);
    this.tray.setToolTip("Ohh Brother");
    this.tray.setContextMenu(this.buildMenu());

    // Update menu periodically when recording (for duration display)
    setInterval(() => {
      if (this.isRecording) {
        this.pythonProcess.send({ command: "status" });
      }
    }, 1000);

    app.on("window-all-closed", (e: Event) => {
      // Don't quit when windows close - we're a menu bar app
      e.preventDefault();
    });
  }
}

// Main entry point
const ohhBrother = new OhhBrotherApp();
ohhBrother.start().catch(console.error);
