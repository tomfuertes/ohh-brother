import * as fs from "fs";
import * as path from "path";

export interface TranscriptFile {
  path: string;
  name: string;
  displayName: string;
  date: Date;
  duration?: string;
}

export class HistoryManager {
  private transcriptsDir: string;

  constructor(transcriptsDir: string) {
    this.transcriptsDir = transcriptsDir;
    this.ensureDir();
  }

  private ensureDir(): void {
    try {
      fs.mkdirSync(this.transcriptsDir, { recursive: true });
    } catch (e) {
      // Directory may already exist
    }
  }

  getRecentFiles(limit: number = 20): TranscriptFile[] {
    try {
      const files = fs.readdirSync(this.transcriptsDir);
      const mdFiles = files
        .filter((f) => f.endsWith(".md"))
        .map((name) => {
          const filePath = path.join(this.transcriptsDir, name);
          const stat = fs.statSync(filePath);

          // Parse date from filename (YYYY-MM-DD_HH-MM.md)
          const match = name.match(/(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})\.md/);
          let date: Date;
          if (match) {
            date = new Date(
              parseInt(match[1]),
              parseInt(match[2]) - 1,
              parseInt(match[3]),
              parseInt(match[4]),
              parseInt(match[5])
            );
          } else {
            date = stat.mtime;
          }

          // Try to extract duration from file content
          let duration: string | undefined;
          try {
            const content = fs.readFileSync(filePath, "utf-8");
            const durationMatch = content.match(/Duration:\s*(.+)/);
            if (durationMatch) {
              duration = durationMatch[1].trim();
            }
          } catch {
            // Ignore read errors
          }

          // Format display name
          const displayName = this.formatDisplayName(date, duration);

          return {
            path: filePath,
            name,
            displayName,
            date,
            duration,
          };
        })
        .sort((a, b) => b.date.getTime() - a.date.getTime())
        .slice(0, limit);

      return mdFiles;
    } catch (e) {
      console.error("Failed to list transcripts:", e);
      return [];
    }
  }

  private formatDisplayName(date: Date, duration?: string): string {
    const dateStr = date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    });
    const timeStr = date.toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
    const durationStr = duration ? ` - ${duration}` : "";
    return `${dateStr} ${timeStr}${durationStr}`;
  }

  readTranscript(filePath: string): string | null {
    try {
      return fs.readFileSync(filePath, "utf-8");
    } catch (e) {
      console.error("Failed to read transcript:", e);
      return null;
    }
  }

  deleteOlderThan(days: number): number {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - days);

    let deleted = 0;

    try {
      const files = this.getRecentFiles(1000); // Get all files
      for (const file of files) {
        if (days === 0 || file.date < cutoff) {
          try {
            fs.unlinkSync(file.path);
            deleted++;
          } catch (e) {
            console.error(`Failed to delete ${file.path}:`, e);
          }
        }
      }
    } catch (e) {
      console.error("Failed to delete old transcripts:", e);
    }

    return deleted;
  }
}
