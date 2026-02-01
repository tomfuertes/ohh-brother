import { contextBridge, ipcRenderer } from "electron";

// Expose a limited API to the renderer
contextBridge.exposeInMainWorld("ohhBrother", {
  // Settings
  getSettings: () => ipcRenderer.invoke("get-settings"),
  saveSettings: (settings: any) => ipcRenderer.invoke("save-settings", settings),

  // Summarization
  onSummarize: (callback: (data: any) => void) => {
    ipcRenderer.on("summarize", (_event, data) => callback(data));
  },

  // LLM API calls (done in renderer to avoid bundling issues)
  summarizeWithClaude: async (apiKey: string, model: string, transcript: string) => {
    const response = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model,
        max_tokens: 2048,
        messages: [
          {
            role: "user",
            content: `Please summarize the following meeting transcript. Include:
1. Key discussion points
2. Decisions made
3. Action items (if any)
4. Notable quotes or highlights

Transcript:
${transcript}`,
          },
        ],
      }),
    });
    const data = await response.json();
    return data.content?.[0]?.text || "No summary generated";
  },

  summarizeWithOpenAI: async (apiKey: string, model: string, transcript: string) => {
    const response = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model,
        messages: [
          {
            role: "system",
            content: "You are a helpful assistant that summarizes meeting transcripts.",
          },
          {
            role: "user",
            content: `Please summarize the following meeting transcript. Include:
1. Key discussion points
2. Decisions made
3. Action items (if any)
4. Notable quotes or highlights

Transcript:
${transcript}`,
          },
        ],
      }),
    });
    const data = await response.json();
    return data.choices?.[0]?.message?.content || "No summary generated";
  },
});
