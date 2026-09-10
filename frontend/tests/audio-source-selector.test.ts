import { describe, it, expect, beforeEach, afterEach } from "vitest";
import {
  AudioSourceSelector,
  type AudioSourceClient,
  type AudioSourceSnapshot,
} from "../src/audio-source-selector";

const FAKE_DEVICES: MediaDeviceInfo[] = [
  { deviceId: "default", groupId: "g1", kind: "audioinput", label: "Default – Built-in Mic", toJSON: () => ({}) } as MediaDeviceInfo,
  { deviceId: "usb-mic-1", groupId: "g2", kind: "audioinput", label: "USB Microphone", toJSON: () => ({}) } as MediaDeviceInfo,
  { deviceId: "cam-mic", groupId: "g3", kind: "audioinput", label: "Webcam Mic", toJSON: () => ({}) } as MediaDeviceInfo,
  { deviceId: "video-out", groupId: "g4", kind: "videoinput", label: "Camera", toJSON: () => ({}) } as MediaDeviceInfo,
];

async function fakeEnumerate(): Promise<MediaDeviceInfo[]> {
  return FAKE_DEVICES;
}

/**
 * A stand-in for the backend. It records what the frontend sent and replays a
 * snapshot the test controls, so the selector can be observed as a pure display
 * of whatever the backend reports.
 */
class FakeAudioSourceClient implements AudioSourceClient {
  registeredWith: { id: string; label: string }[] | null = null;
  setActiveCalls: string[] = [];
  snapshot: AudioSourceSnapshot;
  private readonly onSetActive?: (id: string) => AudioSourceSnapshot;

  constructor(
    snapshot: AudioSourceSnapshot,
    onSetActive?: (id: string) => AudioSourceSnapshot
  ) {
    this.snapshot = snapshot;
    this.onSetActive = onSetActive;
  }

  async registerSources(
    sources: { id: string; label: string }[]
  ): Promise<AudioSourceSnapshot> {
    this.registeredWith = sources;
    return this.snapshot;
  }

  async setActive(id: string): Promise<AudioSourceSnapshot> {
    this.setActiveCalls.push(id);
    this.snapshot = this.onSetActive
      ? this.onSetActive(id)
      : { ...this.snapshot, active: id };
    return this.snapshot;
  }
}

describe("Audio Source Selection (display of backend selection)", () => {
  let container: HTMLElement;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
  });

  afterEach(() => {
    container.remove();
  });

  it("renders one option per source the backend reports", async () => {
    const client = new FakeAudioSourceClient({
      sources: [
        { id: "default", label: "Default – Built-in Mic" },
        { id: "usb-mic-1", label: "USB Microphone" },
      ],
      active: "default",
    });
    const selector = new AudioSourceSelector(container, client, fakeEnumerate);
    await selector.render();

    const options = container.querySelectorAll("select[data-audio-source] option");
    expect(Array.from(options).map((o) => (o as HTMLOptionElement).value)).toEqual([
      "default",
      "usb-mic-1",
    ]);
    expect(Array.from(options).map((o) => o.textContent)).toEqual([
      "Default – Built-in Mic",
      "USB Microphone",
    ]);
  });

  it("sends the OS audioinput devices to the backend, excluding non-audio inputs", async () => {
    const client = new FakeAudioSourceClient({
      sources: [{ id: "default", label: "Default – Built-in Mic" }],
      active: "default",
    });
    const selector = new AudioSourceSelector(container, client, fakeEnumerate);
    await selector.render();

    expect(client.registeredWith).toEqual([
      { id: "default", label: "Default – Built-in Mic" },
      { id: "usb-mic-1", label: "USB Microphone" },
      { id: "cam-mic", label: "Webcam Mic" },
    ]);
  });

  it("selects the option the backend marks active, doing no default-picking of its own", async () => {
    // Backend's active is neither the first option nor the id "default".
    const client = new FakeAudioSourceClient({
      sources: [
        { id: "default", label: "Default – Built-in Mic" },
        { id: "usb-mic-1", label: "USB Microphone" },
        { id: "cam-mic", label: "Webcam Mic" },
      ],
      active: "usb-mic-1",
    });
    const selector = new AudioSourceSelector(container, client, fakeEnumerate);
    await selector.render();

    const select = container.querySelector("select[data-audio-source]") as HTMLSelectElement;
    expect(select.value).toBe("usb-mic-1");
  });

  it("activeDeviceId reflects the backend's active source after render", async () => {
    const client = new FakeAudioSourceClient({
      sources: [
        { id: "default", label: "Default – Built-in Mic" },
        { id: "usb-mic-1", label: "USB Microphone" },
      ],
      active: "usb-mic-1",
    });
    const selector = new AudioSourceSelector(container, client, fakeEnumerate);
    await selector.render();

    expect(selector.activeDeviceId).toBe("usb-mic-1");
  });

  it("routes a user's device change through the backend and reflects the result", async () => {
    const client = new FakeAudioSourceClient({
      sources: [
        { id: "default", label: "Default – Built-in Mic" },
        { id: "usb-mic-1", label: "USB Microphone" },
      ],
      active: "default",
    });
    const selector = new AudioSourceSelector(container, client, fakeEnumerate);
    await selector.render();

    const select = container.querySelector("select[data-audio-source]") as HTMLSelectElement;
    select.value = "usb-mic-1";
    select.dispatchEvent(new Event("change"));
    await Promise.resolve();
    await Promise.resolve();

    expect(client.setActiveCalls).toEqual(["usb-mic-1"]);
    expect(selector.activeDeviceId).toBe("usb-mic-1");
  });

  it("shows the backend's decision, not the user's pick, when the backend overrides it", async () => {
    // Backend refuses the change and keeps "default" active.
    const client = new FakeAudioSourceClient(
      {
        sources: [
          { id: "default", label: "Default – Built-in Mic" },
          { id: "usb-mic-1", label: "USB Microphone" },
        ],
        active: "default",
      },
      () => ({
        sources: [
          { id: "default", label: "Default – Built-in Mic" },
          { id: "usb-mic-1", label: "USB Microphone" },
        ],
        active: "default",
      })
    );
    const selector = new AudioSourceSelector(container, client, fakeEnumerate);
    await selector.render();

    const select = container.querySelector("select[data-audio-source]") as HTMLSelectElement;
    select.value = "usb-mic-1";
    select.dispatchEvent(new Event("change"));
    await Promise.resolve();
    await Promise.resolve();

    const after = container.querySelector("select[data-audio-source]") as HTMLSelectElement;
    expect(after.value).toBe("default");
    expect(selector.activeDeviceId).toBe("default");
  });
});
