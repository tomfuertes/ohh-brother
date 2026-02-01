import * as fs from "fs";
import * as path from "path";

export interface LLMSettings {
  provider: "anthropic" | "openai";
  apiKey: string;
  model: string;
}

export interface RecordingSettings {
  chunkMinutes: number;
  sampleRate: number;
}

export interface HistorySettings {
  maxAgeDays: number;
}

export interface Settings {
  llm?: LLMSettings;
  recording: RecordingSettings;
  history: HistorySettings;
}

const DEFAULT_SETTINGS: Settings = {
  recording: {
    chunkMinutes: 60,
    sampleRate: 16000,
  },
  history: {
    maxAgeDays: 90,
  },
};

export class SettingsManager {
  private configPath: string;
  private settings: Settings;

  constructor(configPath: string) {
    this.configPath = configPath;
    this.settings = this.load();
  }

  private load(): Settings {
    try {
      if (fs.existsSync(this.configPath)) {
        const content = fs.readFileSync(this.configPath, "utf-8");
        const loaded = JSON.parse(content);
        return { ...DEFAULT_SETTINGS, ...loaded };
      }
    } catch (e) {
      console.error("Failed to load settings:", e);
    }
    return { ...DEFAULT_SETTINGS };
  }

  save(): void {
    try {
      fs.mkdirSync(path.dirname(this.configPath), { recursive: true });
      fs.writeFileSync(this.configPath, JSON.stringify(this.settings, null, 2));
    } catch (e) {
      console.error("Failed to save settings:", e);
    }
  }

  get(): Settings {
    return this.settings;
  }

  set(settings: Partial<Settings>): void {
    this.settings = { ...this.settings, ...settings };
    this.save();
  }

  setLLM(llm: LLMSettings): void {
    this.settings.llm = llm;
    this.save();
  }

  getLLM(): LLMSettings | undefined {
    return this.settings.llm;
  }
}
