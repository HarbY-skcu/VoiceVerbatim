/**
 * Consumes the backend's transcription-results WebSocket
 * (`/api/recording/results`, ticket 13) and reflects each `{text, final}`
 * message out to a caller-supplied callback.
 *
 * Deliberately separate from `RecordingClient`: that interface's own
 * doc comment frames it strictly around lifecycle-state transitions
 * (start/stop), while this is a content stream (transcribed text
 * arriving over time) -- a different concern, kept out of that boundary
 * rather than bolted onto it.
 *
 * Purely reactive: this class never closes the socket itself and never
 * runs its own timeout/retry logic. The backend closes the socket once it
 * forwards a `final=true` result (or the connection just drops); this
 * class only ever reacts to whatever the server does, per the agreed
 * "server owns the truth of when results are exhausted" rule.
 */

import type { SocketLike } from "./mic-stream";

export interface TranscriptResult {
  text: string;
  final: boolean;
}

export interface TranscriptResultsClientDeps {
  createSocket(url: string): SocketLike;
}

/** Minimal shape of the browser's WebSocket message event this class needs. */
export interface MessageEventLike {
  data: string;
}

export interface SocketLikeWithMessages extends SocketLike {
  onmessage: ((event: MessageEventLike) => void) | null;
}

export interface TranscriptResultsClient {
  /**
   * Opens the results socket and begins delivering results to `onResult`.
   * `onUnexpectedClose`, if given, fires when the socket closes for any
   * reason *other* than this client's own `disconnect()` having been
   * called -- i.e. the backend ended the Recording on its own (Silence
   * Timeout, Navigation Stop from another tab, a dropped audio socket)
   * and this client had no way to know until the socket told it. Callers
   * use this to resync their displayed state with the backend's.
   */
  connect(
    onResult: (result: TranscriptResult) => void,
    onUnexpectedClose?: () => void
  ): void;
  /** Closes the socket, if still open. A no-op if already closed. */
  disconnect(): void;
}

export class WebSocketTranscriptResultsClient implements TranscriptResultsClient {
  private socket: SocketLikeWithMessages | null = null;
  /**
   * Set right before this client closes the socket itself, so the
   * resulting `onclose` can tell "I closed this" apart from "the backend
   * closed this on me" and only fire `onUnexpectedClose` for the latter.
   */
  private closingIntentionally = false;

  constructor(
    private readonly resultsUrl: string,
    private readonly deps: TranscriptResultsClientDeps
  ) {}

  connect(
    onResult: (result: TranscriptResult) => void,
    onUnexpectedClose?: () => void
  ): void {
    this.closingIntentionally = false;
    const socket = this.deps.createSocket(this.resultsUrl) as SocketLikeWithMessages;
    this.socket = socket;
    socket.onmessage = (event: MessageEventLike) => {
      const parsed = JSON.parse(event.data) as TranscriptResult;
      onResult(parsed);
    };
    socket.onclose = () => {
      // Purely reactive: the server already decided results are
      // exhausted (the Recording ended, or the connection dropped).
      // Just drop the reference; no client-side timeout or retry.
      const wasIntentional = this.closingIntentionally;
      this.socket = null;
      this.closingIntentionally = false;
      if (!wasIntentional) {
        onUnexpectedClose?.();
      }
    };
  }

  disconnect(): void {
    if (this.socket !== null) {
      this.closingIntentionally = true;
      this.socket.close();
      this.socket = null;
    }
  }
}

const DEFAULT_RESULTS_WS_URL = "ws://127.0.0.1:8000/api/recording/results";

/** Default browser-backed dependencies for production use. */
export function createBrowserTranscriptResultsClient(
  resultsUrl: string = DEFAULT_RESULTS_WS_URL
): WebSocketTranscriptResultsClient {
  return new WebSocketTranscriptResultsClient(resultsUrl, {
    createSocket: (url) => new WebSocket(url) as unknown as SocketLike,
  });
}
