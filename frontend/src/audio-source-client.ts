import type {
  AudioSourceClient,
  AudioSourceSnapshot,
} from "./audio-source-selector.js";

const DEFAULT_BASE_URL = "http://127.0.0.1:8000";

/**
 * Talks to the FastAPI backend, which owns the Audio Source selection. The
 * frontend never decides the default or validates a choice — it only registers
 * the OS device list and asks the backend to change the active source.
 */
export class HttpAudioSourceClient implements AudioSourceClient {
  constructor(private readonly baseUrl: string = DEFAULT_BASE_URL) {}

  async registerSources(
    sources: { id: string; label: string }[]
  ): Promise<AudioSourceSnapshot> {
    return this.send("PUT", "/api/audio/sources", { sources });
  }

  async setActive(id: string): Promise<AudioSourceSnapshot> {
    return this.send("PUT", "/api/audio/sources/active", { id });
  }

  private async send(
    method: string,
    path: string,
    body: unknown
  ): Promise<AudioSourceSnapshot> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      throw new Error(`${method} ${path} failed: ${response.status}`);
    }
    return (await response.json()) as AudioSourceSnapshot;
  }
}
