import type { RecordingClient, RecordingState } from "./recording-client";
import { RecordingRejected } from "./recording-client";
import type { MicStreamer } from "./mic-stream";

/**
 * Renders the Record / Pause / Resume / Stop toolbar controls. The backend
 * owns the Recording lifecycle state machine (see `recording.py`); this
 * component only asks it to attempt a transition and displays whatever
 * state comes back. A rejected transition (409) leaves the displayed state
 * unchanged — it never guesses or applies the transition locally.
 */
export class RecordingControls {
  private state: RecordingState = "idle";

  constructor(
    private readonly root: HTMLElement,
    private readonly client: RecordingClient,
    private readonly micStreamer?: MicStreamer
  ) {}

  async render(): Promise<void> {
    const snapshot = await this.client.getState();
    this.state = snapshot.state;
    this.paint();
  }

  /** Whether the Note's text content should be editable in the current state. */
  get isTextEditable(): boolean {
    return this.state !== "recording";
  }

  private paint(): void {
    this.root.innerHTML = this.html();
    this.attachEvents();
  }

  private html(): string {
    if (this.state === "idle") {
      return `<button data-action="record">Record</button>`;
    }
    if (this.state === "recording") {
      return `
        <button data-action="pause">Pause</button>
        <button data-action="stop">Stop</button>
      `;
    }
    // paused
    return `
      <button data-action="resume">Resume</button>
      <button data-action="stop">Stop</button>
    `;
  }

  private attachEvents(): void {
    this.bind("record", () => this.client.start());
    this.bind("pause", () => this.client.pause());
    this.bind("resume", () => this.client.resume());
    this.bind("stop", () => this.client.stop());
  }

  private bind(action: string, transition: () => ReturnType<RecordingClient["start"]>): void {
    const el = this.root.querySelector(`[data-action="${action}"]`);
    el?.addEventListener("click", async () => {
      try {
        const snapshot = await transition();
        this.state = snapshot.state;
        if (this.micStreamer) {
          await this.syncMicStreamer();
        }
      } catch (err) {
        if (!(err instanceof RecordingRejected)) {
          throw err;
        }
        // Rejected: keep displaying the current state, and leave the mic
        // streamer untouched — the backend never committed a transition.
      }
      this.paint();
    });
  }

  /**
   * Keeps mic capture in lockstep with whatever state the backend just
   * confirmed: streaming while "recording", stopped otherwise. Driven by
   * the resulting state rather than the action name so Record and Resume
   * (both -> "recording") and Pause and Stop (both -> not "recording")
   * are handled uniformly.
   */
  private async syncMicStreamer(): Promise<void> {
    if (!this.micStreamer) {
      return;
    }
    try {
      if (this.state === "recording") {
        await this.micStreamer.start();
      } else {
        await this.micStreamer.stop();
      }
    } catch (err) {
      // Mic capture is best-effort relative to the already-committed
      // Recording state transition (e.g. the user denied mic permission,
      // or a device was unplugged): surfacing this as an uncaught error
      // would leave the UI stuck mid-transition even though the backend
      // already moved on. Logged so it's not silent.
      console.error("Mic streamer failed to sync with Recording state:", err);
    }
  }
}
