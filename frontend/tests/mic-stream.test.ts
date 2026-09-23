import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  MicWebSocketStreamer,
  type MediaStreamLike,
  type MediaTrackLike,
  type RecorderLike,
  type SocketLike,
} from "../src/mic-stream";

/** A stand-in for a MediaStreamTrack: just enough to observe `.stop()`. */
class FakeTrack implements MediaTrackLike {
  stopped = false;
  stop(): void {
    this.stopped = true;
  }
}

/** A stand-in for a MediaStream returned by getUserMedia. */
class FakeMediaStream implements MediaStreamLike {
  tracks = [new FakeTrack(), new FakeTrack()];
  getTracks(): MediaTrackLike[] {
    return this.tracks;
  }
}

/** A stand-in for a MediaRecorder: records start/stop and lets tests fire data events. */
class FakeRecorder implements RecorderLike {
  state: "inactive" | "recording" = "inactive";
  startedWithTimeslice: number | undefined;
  ondataavailable: ((event: { data: { size: number } }) => void) | null = null;

  start(timeslice?: number): void {
    this.state = "recording";
    this.startedWithTimeslice = timeslice;
  }

  stop(): void {
    this.state = "inactive";
  }

  emit(size: number): void {
    this.ondataavailable?.({ data: { size } });
  }
}

/** A stand-in for a WebSocket: records what was sent and lets tests drive open/close. */
class FakeSocket implements SocketLike {
  static readonly OPEN = 1;
  readyState = 0;
  onopen: (() => void) | null = null;
  onerror: ((ev: unknown) => void) | null = null;
  onclose: (() => void) | null = null;
  sent: unknown[] = [];
  closed = false;

  send(data: unknown): void {
    this.sent.push(data);
  }

  close(): void {
    this.closed = true;
    this.readyState = 3;
    this.onclose?.();
  }

  open(): void {
    this.readyState = FakeSocket.OPEN;
    this.onopen?.();
  }
}

describe("MicWebSocketStreamer", () => {
  let mediaStream: FakeMediaStream;
  let recorder: FakeRecorder;
  let socket: FakeSocket;
  let getMedia: ReturnType<typeof vi.fn>;
  let createRecorder: ReturnType<typeof vi.fn>;
  let createSocket: ReturnType<typeof vi.fn>;
  let streamer: MicWebSocketStreamer;

  beforeEach(() => {
    mediaStream = new FakeMediaStream();
    recorder = new FakeRecorder();
    socket = new FakeSocket();
    getMedia = vi.fn(async () => mediaStream as MediaStreamLike);
    createRecorder = vi.fn(() => recorder as RecorderLike);
    createSocket = vi.fn(() => socket as SocketLike);
    streamer = new MicWebSocketStreamer(
      "ws://127.0.0.1:8000/api/recording/stream",
      { getMedia, createRecorder, createSocket }
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("acquires the microphone and opens a socket to the stream endpoint on start", async () => {
    const startPromise = streamer.start();
    socket.open();
    await startPromise;

    expect(getMedia).toHaveBeenCalledTimes(1);
    expect(createSocket).toHaveBeenCalledWith(
      "ws://127.0.0.1:8000/api/recording/stream"
    );
  });

  it("begins recording only once the socket is open", async () => {
    const startPromise = streamer.start();
    expect(recorder.state).toBe("inactive");

    socket.open();
    await startPromise;

    expect(recorder.state).toBe("recording");
  });

  it("forwards captured audio chunks over the open socket", async () => {
    const startPromise = streamer.start();
    socket.open();
    await startPromise;

    recorder.emit(128);

    expect(socket.sent).toHaveLength(1);
  });

  it("does not forward empty chunks", async () => {
    const startPromise = streamer.start();
    socket.open();
    await startPromise;

    recorder.emit(0);

    expect(socket.sent).toHaveLength(0);
  });

  it("stop halts the recorder, releases mic tracks, and closes the socket", async () => {
    const startPromise = streamer.start();
    socket.open();
    await startPromise;

    await streamer.stop();

    expect(recorder.state).toBe("inactive");
    expect(mediaStream.tracks.every((t) => t.stopped)).toBe(true);
    expect(socket.closed).toBe(true);
  });

  it("start is idempotent while already streaming", async () => {
    const startPromise = streamer.start();
    socket.open();
    await startPromise;

    await streamer.start();

    expect(getMedia).toHaveBeenCalledTimes(1);
  });

  it("re-acquires the microphone after a stop/start cycle", async () => {
    const first = streamer.start();
    socket.open();
    await first;
    await streamer.stop();

    const second = streamer.start();
    socket.open();
    await second;

    expect(getMedia).toHaveBeenCalledTimes(2);
  });

  it("passes the selected device id through to getUserMedia when provided", async () => {
    streamer = new MicWebSocketStreamer(
      "ws://127.0.0.1:8000/api/recording/stream",
      { getMedia, createRecorder, createSocket, deviceIdProvider: () => "usb-mic-1" }
    );

    const startPromise = streamer.start();
    socket.open();
    await startPromise;

    expect(getMedia).toHaveBeenCalledWith("usb-mic-1");
  });
});
