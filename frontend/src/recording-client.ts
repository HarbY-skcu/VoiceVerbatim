export type RecordingState = "idle" | "recording" | "paused";

export interface RecordingSnapshot {
  state: RecordingState;
}

/**
 * Talks to the FastAPI backend, which owns the Recording lifecycle state
 * machine. The frontend never decides whether a transition is legal — it
 * only asks the backend to attempt one and reflects whatever state comes
 * back (or the rejection).
 */
export interface RecordingClient {
  getState(): Promise<RecordingSnapshot>;
  start(): Promise<RecordingSnapshot>;
  pause(): Promise<RecordingSnapshot>;
  resume(): Promise<RecordingSnapshot>;
  stop(): Promise<RecordingSnapshot>;
}

const DEFAULT_BASE_URL = "http://127.0.0.1:8000";

export class RecordingRejected extends Error {}

export class HttpRecordingClient implements RecordingClient {
  constructor(private readonly baseUrl: string = DEFAULT_BASE_URL) {}

  async getState(): Promise<RecordingSnapshot> {
    const response = await fetch(`${this.baseUrl}/api/recording`);
    return (await response.json()) as RecordingSnapshot;
  }

  start(): Promise<RecordingSnapshot> {
    return this.post("/api/recording/start");
  }

  pause(): Promise<RecordingSnapshot> {
    return this.post("/api/recording/pause");
  }

  resume(): Promise<RecordingSnapshot> {
    return this.post("/api/recording/resume");
  }

  stop(): Promise<RecordingSnapshot> {
    return this.post("/api/recording/stop");
  }

  private async post(path: string): Promise<RecordingSnapshot> {
    const response = await fetch(`${this.baseUrl}${path}`, { method: "POST" });
    if (response.status === 409) {
      const body = await response.json();
      throw new RecordingRejected(body.detail ?? "Recording transition rejected");
    }
    if (!response.ok) {
      throw new Error(`POST ${path} failed: ${response.status}`);
    }
    return (await response.json()) as RecordingSnapshot;
  }
}
