export type RecordingState = "idle" | "recording" | "paused";

/**
 * The batch transcription result the backend inlines into Pause/Stop
 * responses (ticket 04's `result["transcription"]`). Ticket 13 wires this
 * up on the frontend for the first time -- previously present in every
 * response but never read here. `inserted` is the text just committed to
 * the Note (or null if nothing was buffered); `error` is a
 * non-Note-corrupting transcription failure message, if any.
 */
export interface BatchTranscriptionResult {
  inserted: string | null;
  error: string | null;
}

export interface RecordingSnapshot {
  state: RecordingState;
  /** Only present on Pause/Stop responses, which flush the audio buffer for transcription. */
  transcription?: BatchTranscriptionResult;
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
  /** Reports a transcribed speech event, resetting the Silence Timeout window. */
  notifySpeech(): Promise<void>;
  /**
   * Called when the user navigates away from the current Note view while a
   * Recording may be active. Behaves identically to a manual Stop; a no-op
   * if nothing is active.
   */
  navigationStop(): Promise<RecordingSnapshot>;
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

  async notifySpeech(): Promise<void> {
    await fetch(`${this.baseUrl}/api/recording/speech`, { method: "POST" });
  }

  navigationStop(): Promise<RecordingSnapshot> {
    return this.post("/api/recording/navigation-stop");
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
