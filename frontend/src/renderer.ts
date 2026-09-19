import { Shell } from "./shell.ts";
import { AudioSourceSelector } from "./audio-source-selector.ts";
import { HttpAudioSourceClient } from "./audio-source-client.ts";
import { RecordingControls } from "./recording-controls.ts";
import { HttpRecordingClient } from "./recording-client.ts";

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

  new AudioSourceSelector(audioSourceRegion, new HttpAudioSourceClient())
    .render()
    .catch((err) => {
      console.error("Failed to load audio sources:", err);
      audioSourceRegion.innerHTML = `<p style="color: red; padding: 8px;">Error: ${err.message}</p>`;
    });

  new RecordingControls(recordingRegion, recordingClient)
    .render()
    .catch((err) => {
      console.error("Failed to load recording state:", err);
      recordingRegion.innerHTML = `<p style="color: red; padding: 8px;">Error: ${err.message}</p>`;
    });
}
