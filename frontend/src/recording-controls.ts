import type { BatchTranscriptionResult, RecordingClient, RecordingState } from "./recording-client";
import { RecordingRejected } from "./recording-client";
import type { MicStreamer } from "./mic-stream";

/**
 * Ticket 14: notified whenever a Recording transition completes, so the
 * flowing-transcript view can switch between read-only (while recording)
 * and editable (once stopped/idle) in lockstep with the backend's state.
 *
 * `previousState` is `null` on the initial `render()` snapshot (there is
 * no prior transition to report) and the actual prior state on every
 * subsequent transition. With only two states (`idle`/`recording`),
 * every `idle -> recording` is a fresh Start and every
 * `recording -> idle` is a Stop -- no further disambiguation needed.
 */
export interface RecordingStateObserver {
  onRecordingStateChanged(state: RecordingState, previousState: RecordingState | null): void;
}

/**
 * Renders the Record / Stop toolbar controls. The backend owns the
 * Recording lifecycle state machine (see `recording.py`); this component
 * only asks it to attempt a transition and displays whatever state comes
 * back. A rejected transition (409) leaves the displayed state
 * unchanged — it never guesses or applies the transition locally.
 */
export class RecordingControls {
  private state: RecordingState = "idle";
  /**
   * The most recent batch transcription result (ticket 13's fix for the
   * dead `result["transcription"]` field, previously present on every
   * Stop response but never read anywhere on the frontend). Each new
   * Stop response overwrites this outright rather than appending -- it
   * mirrors whatever the backend just committed to the Note, not a
   * running log of every transcription attempt.
   */
  private lastTranscription: BatchTranscriptionResult | null = null;

  constructor(
    private readonly root: HTMLElement,
    private readonly client: RecordingClient,
    private readonly micStreamer?: MicStreamer,
    private readonly stateObserver?: RecordingStateObserver
  ) {}

  /** The most recently displayed batch transcription result, if any. */
  get transcription(): BatchTranscriptionResult | null {
    return this.lastTranscription;
  }

  async render(): Promise<void> {
    const previousState = this.state;
    const snapshot = await this.client.getState();
    this.state = snapshot.state;
    // No prior transition to report on the initial snapshot -- callers
    // must not treat this as a fresh Start just because state happens to
    // be "recording" (e.g. a page reload mid-session).
    this.stateObserver?.onRecordingStateChanged(this.state, null);
    if (this.micStreamer && previousState !== this.state) {
      // Resync (Silence Timeout merge): if this render() is being called
      // because the backend ended the Recording on its own (the results
      // socket closed unexpectedly) rather than through a button click,
      // nothing else will have told the mic streamer to stop.
      await this.syncMicStreamer();
    }
    this.paint();
  }

  /**
   * Whether the Note's text content should be editable in the current
   * state. Ticket 14: cursor repositioning (and therefore editing) is
   * only meaningful once fully stopped (`idle`).
   */
  get isTextEditable(): boolean {
    return this.state === "idle";
  }

  private paint(): void {
    this.root.innerHTML = this.html();
    this.attachEvents();
  }

  private html(): string {
    if (this.state === "idle") {
      return `<button data-action="record">Record</button>`;
    }
    return `<button data-action="stop">Stop</button>`;
  }

  private attachEvents(): void {
    this.bind("record", () => this.client.start());
    this.bind("stop", () => this.client.stop());
  }

  private bind(action: string, transition: () => ReturnType<RecordingClient["start"]>): void {
    const el = this.root.querySelector(`[data-action="${action}"]`);
    el?.addEventListener("click", async () => {
      const previousState = this.state;
      try {
        const snapshot = await transition();
        this.state = snapshot.state;
        // Stop responses carry a fresh batch transcription result;
        // overwrite whatever was displayed before rather than appending,
        // per the agreed "replace, don't accumulate" rule for this field.
        // Set *before* notifying the observer so it can synchronously read
        // `this.transcription` inside `onRecordingStateChanged` and feed it
        // into TranscriptView (ticket 14: the batch path is no longer dead
        // code -- see renderer.ts).
        if (snapshot.transcription !== undefined) {
          this.lastTranscription = snapshot.transcription;
        }
        this.stateObserver?.onRecordingStateChanged(this.state, previousState);
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
   * confirmed: streaming while "recording", stopped otherwise.
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
