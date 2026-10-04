import { Shell } from "./shell.ts";
import { AudioSourceSelector } from "./audio-source-selector.ts";
import { HttpAudioSourceClient } from "./audio-source-client.ts";
import { RecordingControls } from "./recording-controls.ts";
import { HttpRecordingClient } from "./recording-client.ts";
import type { RecordingSnapshot } from "./recording-client.ts";
import { createBrowserMicStreamer } from "./mic-stream.ts";
import { TranscriptView } from "./transcript-view.ts";
import { HttpNoteClient } from "./note-client.ts";
import { createBrowserTranscriptResultsClient } from "./transcript-results-client.ts";

const root = document.getElementById("app")!;
const recordingClient = new HttpRecordingClient();

// Ticket 14: the frontend now owns composition/positioning, including
// manual edits made while idle. Those are debounced (~2s) inside
// TranscriptView, but navigating away from the Note view must not lose
// up to 2s of unsaved edits -- so navigationStop (routed through Shell)
// flushes any pending debounced save first, before telling the backend
// about the navigation. `transcriptView` is assigned further down, once
// the main pane exists; this wrapper reads it lazily via closure so
// construction order here doesn't matter.
let transcriptView: TranscriptView | null = null;
const navigationNotifier = {
  async navigationStop(): Promise<RecordingSnapshot> {
    transcriptView?.flushPendingEdits();
    return recordingClient.navigationStop();
  },
};

const shell = new Shell(root, navigationNotifier);
shell.render();

const toolbar = root.querySelector(
  '[data-region="recording-toolbar"]'
) as HTMLElement | null;
if (toolbar) {
  const audioSourceRegion = document.createElement("div");
  const recordingRegion = document.createElement("div");
  toolbar.append(audioSourceRegion, recordingRegion);

  const audioSourceSelector = new AudioSourceSelector(
    audioSourceRegion,
    new HttpAudioSourceClient()
  );
  audioSourceSelector.render().catch((err) => {
    console.error("Failed to load audio sources:", err);
    audioSourceRegion.innerHTML = `<p style="color: red; padding: 8px;">Error: ${err.message}</p>`;
  });

  // The mic streamer requests whichever Audio Source is active at the
  // moment recording starts, so a device switch made before hitting
  // Record is honoured without the two components needing a tighter
  // coupling than this read-only lookup.
  const micStreamer = createBrowserMicStreamer(
    () => audioSourceSelector.activeDeviceId || undefined
  );

  const mainPane = root.querySelector(
    '[data-region="main-pane"]'
  ) as HTMLElement | null;

  const noteClient = new HttpNoteClient();
  const resultsClient = createBrowserTranscriptResultsClient();

  if (mainPane) {
    transcriptView = new TranscriptView(mainPane, {
      // Ticket 14: the frontend is the sole authority on composition/
      // positioning now -- every change (transcription result or manual
      // edit) is pushed back to the backend as a full-text overwrite.
      // Transcription results/forced flushes report immediately;
      // manual edits are already debounced inside TranscriptView by the
      // time this fires.
      onTextChanged: (text) => {
        noteClient
          .updateActiveNote(text)
          .catch((err) => console.error("Failed to save active note:", err));
      },
    });
    noteClient
      .getActiveNote()
      .then((snapshot) => {
        if (snapshot.title) {
          transcriptView!.setTitle(snapshot.title);
        }
        if (snapshot.text) {
          transcriptView!.applyResult({ text: snapshot.text, final: true });
        }
      })
      .catch((err) => console.error("Failed to load active note:", err));
  }

  const controls = new RecordingControls(recordingRegion, recordingClient, micStreamer, {
    onRecordingStateChanged: (state, previousState) => {
      if (!transcriptView) {
        return;
      }
      // Ticket 14: cursor repositioning/editing is only meaningful once
      // fully stopped (idle), matching RecordingControls.isTextEditable.
      transcriptView.setReadOnly(state !== "idle");

      // Entering a recording session (always a fresh Start now) must not
      // start streaming new audio against text the backend hasn't
      // actually received yet -- force through any pending debounced
      // manual-edit save first (ticket 14's "Record forces an immediate
      // flush" rule).
      const isEnteringRecording = state === "recording";
      if (isEnteringRecording) {
        transcriptView.flushPendingEdits();
      }

      // Every idle -> recording transition is a fresh Start, and opens a
      // new results connection. The initial render() snapshot
      // (`previousState === null`) is never a transition, so it never
      // triggers this either; existing `getActiveNote()` hydration above
      // already covers load/refresh.
      const isFreshStart = previousState === "idle" && state === "recording";
      if (isFreshStart) {
        noteClient
          .getActiveNote()
          .then((snapshot) => {
            if (snapshot.title) {
              transcriptView!.setTitle(snapshot.title);
            }
          })
          .catch((err) => console.error("Failed to load active note:", err));
        resultsClient.connect(
          (result) => transcriptView!.applyResult(result),
          () => {
            // The backend ended this Recording on its own (Silence
            // Timeout, or Navigation Stop/Stop from elsewhere) rather
            // than through this tab's own Stop click -- resync displayed
            // state/mic capture with whatever the backend actually landed
            // on, the same way the initial render() does on page load.
            controls.render().catch((err) =>
              console.error("Failed to resync recording state:", err)
            );
          }
        );
      }

      // Stop carries a fresh batch transcription result (ticket 13's
      // previously-dead `transcription` field). Wire it into the same
      // local-splice path streaming results use -- it lands at whatever
      // cursor the frontend is tracking, not appended at the end, and
      // reports immediately (final: true) just like a streamed final.
      const leftRecording = previousState === "recording" && state !== "recording";
      if (leftRecording && controls.transcription?.inserted) {
        transcriptView.applyResult({ text: controls.transcription.inserted, final: true });
      }

      // Stop (-> idle) disconnects as a safety net; the results socket
      // normally closes itself once the backend forwards a final result,
      // but this guards against it still being open.
      if (previousState !== null && state === "idle") {
        resultsClient.disconnect();
      }
    },
  });

  controls.render().catch((err) => {
    console.error("Failed to load recording state:", err);
    recordingRegion.innerHTML = `<p style="color: red; padding: 8px;">Error: ${err.message}</p>`;
  });
}
