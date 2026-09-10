import { Shell } from "./shell.ts";
import { AudioSourceSelector } from "./audio-source-selector.ts";
import { HttpAudioSourceClient } from "./audio-source-client.ts";

const root = document.getElementById("app")!;
const shell = new Shell(root);
shell.render();

const toolbar = root.querySelector(
  '[data-region="recording-toolbar"]'
) as HTMLElement | null;
if (toolbar) {
  new AudioSourceSelector(toolbar, new HttpAudioSourceClient()).render().catch(err => {
    console.error("Failed to load audio sources:", err);
    toolbar.innerHTML = `<p style="color: red; padding: 8px;">Error: ${err.message}</p>`;
  });
}
