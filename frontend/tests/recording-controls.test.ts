import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { RecordingControls } from "../src/recording-controls";
import type {
  RecordingClient,
  RecordingSnapshot,
  RecordingState,
} from "../src/recording-client";
import { RecordingRejected } from "../src/recording-client";

/**
 * A stand-in for the backend Recording state machine. Records which
 * transitions were attempted and replays whatever the test configures,
 * including rejections, so RecordingControls can be observed as a pure
 * display of whatever the backend reports.
 */
class FakeRecordingClient implements RecordingClient {
  calls: string[] = [];
  private state: RecordingState;
  private rejectNext: string | null = null;

  constructor(initial: RecordingState = "idle") {
    this.state = initial;
  }

  rejectNextTransitionWith(message: string): void {
    this.rejectNext = message;
  }

  async getState(): Promise<RecordingSnapshot> {
    return { state: this.state };
  }

  async start(): Promise<RecordingSnapshot> {
    return this.transition("start", "recording");
  }

  async pause(): Promise<RecordingSnapshot> {
    return this.transition("pause", "paused");
  }

  async resume(): Promise<RecordingSnapshot> {
    return this.transition("resume", "recording");
  }

  async stop(): Promise<RecordingSnapshot> {
    return this.transition("stop", "idle");
  }

  private async transition(
    name: string,
    nextState: RecordingState
  ): Promise<RecordingSnapshot> {
    this.calls.push(name);
    if (this.rejectNext) {
      const message = this.rejectNext;
      this.rejectNext = null;
      throw new RecordingRejected(message);
    }
    this.state = nextState;
    return { state: this.state };
  }
}

describe("Record / Stop / Pause controls", () => {
  let container: HTMLElement;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
  });

  afterEach(() => {
    container.remove();
  });

  it("renders a Record button when idle", async () => {
    const client = new FakeRecordingClient("idle");
    const controls = new RecordingControls(container, client);
    await controls.render();

    expect(container.querySelector('[data-action="record"]')).not.toBeNull();
    expect(container.querySelector('[data-action="stop"]')).toBeNull();
  });

  it("clicking Record starts a Recording and shows Pause/Stop", async () => {
    const client = new FakeRecordingClient("idle");
    const controls = new RecordingControls(container, client);
    await controls.render();

    (container.querySelector('[data-action="record"]') as HTMLElement).click();
    await flush();

    expect(client.calls).toEqual(["start"]);
    expect(container.querySelector('[data-action="pause"]')).not.toBeNull();
    expect(container.querySelector('[data-action="stop"]')).not.toBeNull();
    expect(container.querySelector('[data-action="record"]')).toBeNull();
  });

  it("clicking Pause while recording shows Resume and enables text editing", async () => {
    const client = new FakeRecordingClient("recording");
    const controls = new RecordingControls(container, client);
    await controls.render();

    (container.querySelector('[data-action="pause"]') as HTMLElement).click();
    await flush();

    expect(client.calls).toEqual(["pause"]);
    expect(container.querySelector('[data-action="resume"]')).not.toBeNull();
    expect(controls.isTextEditable).toBe(true);
  });

  it("clicking Resume while paused restarts capture", async () => {
    const client = new FakeRecordingClient("paused");
    const controls = new RecordingControls(container, client);
    await controls.render();

    (container.querySelector('[data-action="resume"]') as HTMLElement).click();
    await flush();

    expect(client.calls).toEqual(["resume"]);
    expect(container.querySelector('[data-action="pause"]')).not.toBeNull();
    expect(controls.isTextEditable).toBe(false);
  });

  it("clicking Stop while recording ends the session and returns to idle display", async () => {
    const client = new FakeRecordingClient("recording");
    const controls = new RecordingControls(container, client);
    await controls.render();

    (container.querySelector('[data-action="stop"]') as HTMLElement).click();
    await flush();

    expect(client.calls).toEqual(["stop"]);
    expect(container.querySelector('[data-action="record"]')).not.toBeNull();
  });

  it("text is not editable while actively recording", async () => {
    const client = new FakeRecordingClient("recording");
    const controls = new RecordingControls(container, client);
    await controls.render();

    expect(controls.isTextEditable).toBe(false);
  });

  it("a rejected transition leaves the displayed state unchanged", async () => {
    const client = new FakeRecordingClient("idle");
    client.rejectNextTransitionWith("Cannot start: a Recording is already recording");
    const controls = new RecordingControls(container, client);
    await controls.render();

    (container.querySelector('[data-action="record"]') as HTMLElement).click();
    await flush();

    expect(container.querySelector('[data-action="record"]')).not.toBeNull();
    expect(container.querySelector('[data-action="pause"]')).toBeNull();
  });
});

async function flush(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
}
