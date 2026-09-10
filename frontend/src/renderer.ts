import { Shell } from "./shell.js";
import { AudioSourceSelector } from "./audio-source-selector.js";
import { HttpAudioSourceClient } from "./audio-source-client.js";

const root = document.getElementById("app")!;
const shell = new Shell(root);
shell.render();

const toolbar = root.querySelector(
  '[data-region="recording-toolbar"]'
) as HTMLElement | null;
if (toolbar) {
  void new AudioSourceSelector(toolbar, new HttpAudioSourceClient()).render();
}
