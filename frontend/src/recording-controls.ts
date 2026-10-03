import type { BatchTranscriptionResult, RecordingClient, RecordingState } from "./recording-client";
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
  /**
   * The most recent batch transcription result (ticket 13's fix for the
   * dead `result["transcription"]` field, previously present on every
   * Pause/Stop response but never read anywhere on the frontend). Each
   * new Pause/Stop response overwrites this outright rather than
   * appending -- it mirrors whatever the backend just committed to the
   * Note, not a running log of every transcription attempt.
   */
  private lastTranscription: BatchTranscriptionResult | null = null;

  constructor(
    private readonly root: HTMLElement,
    private readonly client: RecordingClient,
    private readonly micStreamer?: MicStreamer
  ) {}

  /** The most recently displayed batch transcription result, if any. */
  get transcription(): BatchTranscriptionResult | null {
    return this.lastTranscription;
  }

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
        // Pause/Stop responses carry a fresh batch transcription result;
        // overwrite whatever was displayed before rather than appending,
        // per the agreed "replace, don't accumulate" rule for this field.
        if (snapshot.transcription !== undefined) {
          this.lastTranscription = snapshot.transcription;
        }
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
