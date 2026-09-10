import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { AudioSourceSelector } from "../src/audio-source-selector";

const FAKE_DEVICES: MediaDeviceInfo[] = [
  { deviceId: "default", groupId: "g1", kind: "audioinput", label: "Default – Built-in Mic", toJSON: () => ({}) } as MediaDeviceInfo,
  { deviceId: "usb-mic-1", groupId: "g2", kind: "audioinput", label: "USB Microphone", toJSON: () => ({}) } as MediaDeviceInfo,
  { deviceId: "cam-mic", groupId: "g3", kind: "audioinput", label: "Webcam Mic", toJSON: () => ({}) } as MediaDeviceInfo,
  { deviceId: "video-out", groupId: "g4", kind: "videoinput", label: "Camera", toJSON: () => ({}) } as MediaDeviceInfo,
];

async function fakeEnumerate(): Promise<MediaDeviceInfo[]> {
  return FAKE_DEVICES;
}

describe("Audio Source Selection", () => {
  let container: HTMLElement;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
  });

  afterEach(() => {
    container.remove();
  });

  it("dropdown lists only audioinput devices", async () => {
    const selector = new AudioSourceSelector(container, fakeEnumerate);
    await selector.render();

    const options = container.querySelectorAll("select[data-audio-source] option");
    const optionValues = Array.from(options).map((o) => (o as HTMLOptionElement).value);
    expect(optionValues).toContain("default");
    expect(optionValues).toContain("usb-mic-1");
    expect(optionValues).toContain("cam-mic");
    expect(optionValues).not.toContain("video-out");
  });

  it("pre-selects the system default device (deviceId === 'default')", async () => {
    const selector = new AudioSourceSelector(container, fakeEnumerate);
    await selector.render();

    const select = container.querySelector("select[data-audio-source]") as HTMLSelectElement;
    expect(select.value).toBe("default");
  });

  it("pre-selects first device when no device with id 'default' exists", async () => {
    const noDefault: MediaDeviceInfo[] = [
      { deviceId: "mic-a", groupId: "g1", kind: "audioinput", label: "Mic A", toJSON: () => ({}) } as MediaDeviceInfo,
      { deviceId: "mic-b", groupId: "g2", kind: "audioinput", label: "Mic B", toJSON: () => ({}) } as MediaDeviceInfo,
    ];
    const selector = new AudioSourceSelector(container, async () => noDefault);
    await selector.render();

    const select = container.querySelector("select[data-audio-source]") as HTMLSelectElement;
    expect(select.value).toBe("mic-a");
  });

  it("activeDeviceId returns the pre-selected device after render", async () => {
    const selector = new AudioSourceSelector(container, fakeEnumerate);
    await selector.render();

    expect(selector.activeDeviceId).toBe("default");
  });

  it("activeDeviceId updates when user selects a different device", async () => {
    const selector = new AudioSourceSelector(container, fakeEnumerate);
    await selector.render();

    const select = container.querySelector("select[data-audio-source]") as HTMLSelectElement;
    select.value = "usb-mic-1";
    select.dispatchEvent(new Event("change"));

    expect(selector.activeDeviceId).toBe("usb-mic-1");
  });
});
