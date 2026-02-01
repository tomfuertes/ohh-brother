import { spawn, ChildProcess } from "child_process";
import * as path from "path";
import * as fs from "fs";
import * as readline from "readline";

export interface PythonMessage {
  type: string;
  [key: string]: any;
}

export class PythonProcess {
  private process: ChildProcess | null = null;
  private pythonDir: string;
  private outputDir: string;
  private messageCallback: ((msg: PythonMessage) => void) | null = null;
  private errorCallback: ((error: string) => void) | null = null;
  private pidFile: string;

  constructor(pythonDir: string, outputDir: string) {
    this.pythonDir = pythonDir;
    this.outputDir = outputDir;
    this.pidFile = path.join(outputDir, ".transcriber.pid");

    // Cleanup orphaned process on startup
    this.cleanupOrphanedProcess();
  }

  private cleanupOrphanedProcess(): void {
    try {
      if (fs.existsSync(this.pidFile)) {
        const pid = parseInt(fs.readFileSync(this.pidFile, "utf-8").trim(), 10);
        if (pid) {
          try {
            process.kill(pid, "SIGTERM");
            console.log(`Cleaned up orphaned Python process (PID: ${pid})`);
          } catch {
            // Process already dead
          }
        }
        fs.unlinkSync(this.pidFile);
      }
    } catch (e) {
      // Ignore errors
    }
  }

  private writePidFile(pid: number): void {
    try {
      fs.mkdirSync(path.dirname(this.pidFile), { recursive: true });
      fs.writeFileSync(this.pidFile, pid.toString());
    } catch (e) {
      console.error("Failed to write PID file:", e);
    }
  }

  private removePidFile(): void {
    try {
      if (fs.existsSync(this.pidFile)) {
        fs.unlinkSync(this.pidFile);
      }
    } catch (e) {
      // Ignore
    }
  }

  onMessage(callback: (msg: PythonMessage) => void): void {
    this.messageCallback = callback;
  }

  onError(callback: (error: string) => void): void {
    this.errorCallback = callback;
  }

  async start(): Promise<void> {
    if (this.process) {
      return;
    }

    // Find Python executable
    const venvPython = path.join(this.pythonDir, "venv", "bin", "python");
    const pythonExe = fs.existsSync(venvPython) ? venvPython : "python3";

    const scriptPath = path.join(this.pythonDir, "transcriber.py");

    this.process = spawn(pythonExe, [scriptPath, "--output-dir", this.outputDir], {
      cwd: this.pythonDir,
      stdio: ["pipe", "pipe", "pipe"],
      env: {
        ...process.env,
        PYTHONUNBUFFERED: "1",
      },
    });

    if (this.process.pid) {
      this.writePidFile(this.process.pid);
    }

    // Read stdout line by line
    if (this.process.stdout) {
      const rl = readline.createInterface({
        input: this.process.stdout,
        crlfDelay: Infinity,
      });

      rl.on("line", (line) => {
        try {
          const msg = JSON.parse(line) as PythonMessage;
          this.messageCallback?.(msg);
        } catch (e) {
          console.log("Python stdout:", line);
        }
      });
    }

    // Read stderr
    if (this.process.stderr) {
      this.process.stderr.on("data", (data) => {
        const text = data.toString();
        console.error("Python stderr:", text);
        this.errorCallback?.(text);
      });
    }

    // Handle exit
    this.process.on("exit", (code, signal) => {
      console.log(`Python process exited (code: ${code}, signal: ${signal})`);
      this.process = null;
      this.removePidFile();
    });

    this.process.on("error", (err) => {
      console.error("Python process error:", err);
      this.errorCallback?.(err.message);
      this.process = null;
      this.removePidFile();
    });
  }

  send(msg: object): void {
    if (this.process?.stdin) {
      this.process.stdin.write(JSON.stringify(msg) + "\n");
    }
  }

  stop(): void {
    if (this.process) {
      this.send({ command: "quit" });

      // Give it time to clean up
      setTimeout(() => {
        if (this.process) {
          this.process.kill("SIGTERM");
          this.process = null;
        }
        this.removePidFile();
      }, 2000);
    }
  }

  isRunning(): boolean {
    return this.process !== null;
  }
}
