import { Shell } from "./shell.ts";
import { AudioSourceSelector } from "./audio-source-selector.ts";
import { HttpAudioSourceClient } from "./audio-source-client.ts";
import { RecordingControls } from "./recording-controls.ts";
import { HttpRecordingClient } from "./recording-client.ts";
import { createBrowserMicStreamer } from "./mic-stream.ts";

const root = document.getElementById("app")!;
const recordingClient = new HttpRecordingClient();
const shell = new Shell(root, recordingClient);
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
  // Record/Resume is honoured without the two components needing a
  // tighter coupling than this read-only lookup.
  const micStreamer = createBrowserMicStreamer(
    () => audioSourceSelector.activeDeviceId || undefined
  );

  new RecordingControls(recordingRegion, recordingClient, micStreamer)
    .render()
    .catch((err) => {
      console.error("Failed to load recording state:", err);
      recordingRegion.innerHTML = `<p style="color: red; padding: 8px;">Error: ${err.message}</p>`;
    });
}
