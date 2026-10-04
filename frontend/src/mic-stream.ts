/**
 * Mic capture -> `/api/recording/stream` WebSocket (ticket 04.1). The
 * backend's streaming ingest (WebSocket endpoint, orchestrator, Note
 * reconciliation) already exists and is fully tested; this is the missing
 * producer side: acquire the microphone, chunk it via MediaRecorder, and
 * forward each chunk over the socket while it's open.
 *
 * Every browser capability the backend can't see (getUserMedia,
 * MediaRecorder, WebSocket) is behind a small injectable seam so this can
 * be unit-tested without real hardware or a network — mirroring how
 * AudioSourceSelector injects `enumerateDevices`.
 */

export interface MediaTrackLike {
  stop(): void;
}

export interface MediaStreamLike {
  getTracks(): MediaTrackLike[];
}

export interface RecorderDataEvent {
  data: { size: number };
}

export interface RecorderLike {
  state: "inactive" | "recording";
  ondataavailable: ((event: RecorderDataEvent) => void) | null;
  start(timeslice?: number): void;
  stop(): void;
}

export interface SocketLike {
  readyState: number;
  onopen: (() => void) | null;
  onerror: ((ev: unknown) => void) | null;
  onclose: (() => void) | null;
  send(data: unknown): void;
  close(): void;
}

const SOCKET_OPEN = 1;

export interface MicStreamer {
  start(): Promise<void>;
  stop(): Promise<void>;
}

export interface MicWebSocketStreamerDeps {
  getMedia(deviceId?: string): Promise<MediaStreamLike>;
  createRecorder(stream: MediaStreamLike): RecorderLike;
  createSocket(url: string): SocketLike;
  /** Resolves which Audio Source device to request, if any (undefined lets the browser pick). */
  deviceIdProvider?: () => string | undefined;
  /** How often MediaRecorder should emit a chunk, in ms. */
  timesliceMs?: number;
}

/**
 * Streams microphone audio to the backend's real-time transcription ingest.
 * `start()`/`stop()` mirror a Recording's own lifecycle (Record -> start,
 * Stop -> stop) — this class has no state-machine opinions of its own, it
 * only owns the mic-to-socket plumbing.
 */
export class MicWebSocketStreamer implements MicStreamer {
  private stream: MediaStreamLike | null = null;
  private recorder: RecorderLike | null = null;
  private socket: SocketLike | null = null;

  constructor(
    private readonly streamUrl: string,
    private readonly deps: MicWebSocketStreamerDeps
  ) {}

  async start(): Promise<void> {
    if (this.socket !== null) {
      // Already streaming; this is just a defensive no-op for
      // double-clicks.
      return;
    }

    const deviceId = this.deps.deviceIdProvider?.();
    this.stream = await this.deps.getMedia(deviceId);

    const socket = this.deps.createSocket(this.streamUrl);
    this.socket = socket;

    await new Promise<void>((resolve, reject) => {
      socket.onopen = () => resolve();
      socket.onerror = (err) => reject(err);
      // The test double (and, in principle, a real socket under odd
      // scheduling) may already be open by the time these handlers are
      // attached, since creating the socket and registering handlers
      // aren't a single atomic step. Don't wait for an onopen that will
      // never fire again.
      if (socket.readyState === SOCKET_OPEN) {
        resolve();
      }
    });

    const recorder = this.deps.createRecorder(this.stream);
    this.recorder = recorder;
    recorder.ondataavailable = (event) => {
      if (event.data.size === 0) {
        return;
      }
      if (socket.readyState === SOCKET_OPEN) {
        socket.send(event.data);
      }
    };
    recorder.start(this.deps.timesliceMs ?? 250);
  }

  async stop(): Promise<void> {
    if (this.recorder !== null) {
      this.recorder.stop();
      this.recorder = null;
    }
    if (this.stream !== null) {
      this.stream.getTracks().forEach((track) => track.stop());
      this.stream = null;
    }
    if (this.socket !== null) {
      this.socket.close();
      this.socket = null;
    }
  }
}

const DEFAULT_WS_URL = "ws://127.0.0.1:8000/api/recording/stream";

/** Default browser-backed dependencies for production use. */
export function createBrowserMicStreamer(
  deviceIdProvider?: () => string | undefined,
  streamUrl: string = DEFAULT_WS_URL
): MicWebSocketStreamer {
  return new MicWebSocketStreamer(streamUrl, {
    getMedia: (deviceId) =>
      navigator.mediaDevices.getUserMedia({
        audio: deviceId ? { deviceId: { exact: deviceId } } : true,
      }),
    createRecorder: (stream) =>
      new MediaRecorder(stream as unknown as MediaStream) as unknown as RecorderLike,
    createSocket: (url) => new WebSocket(url) as unknown as SocketLike,
    deviceIdProvider,
  });
}
