import { describe, it, expect } from "vitest";
import {
  WebSocketTranscriptResultsClient,
  type MessageEventLike,
  type SocketLikeWithMessages,
  type TranscriptResult,
} from "../src/transcript-results-client";

/** A stand-in for the browser WebSocket, mirroring FakeSocket-style doubles used for mic-stream.test.ts. */
class FakeSocket implements SocketLikeWithMessages {
  readyState = 1;
  onopen: (() => void) | null = null;
  onerror: ((ev: unknown) => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((event: MessageEventLike) => void) | null = null;
  sent: unknown[] = [];
  closed = false;

  send(data: unknown): void {
    this.sent.push(data);
  }

  close(): void {
    this.closed = true;
    this.onclose?.();
  }

  /** Test helper: simulates the server pushing a result. */
  emit(result: TranscriptResult): void {
    this.onmessage?.({ data: JSON.stringify(result) });
  }
}

describe("WebSocketTranscriptResultsClient", () => {
  it("delivers each parsed result to the onResult callback", () => {
    const socket = new FakeSocket();
    const client = new WebSocketTranscriptResultsClient("ws://example/results", {
      createSocket: () => socket,
    });
    const received: TranscriptResult[] = [];

    client.connect((result) => received.push(result));
    socket.emit({ text: "hel", final: false });
    socket.emit({ text: "hello", final: true });

    expect(received).toEqual([
      { text: "hel", final: false },
      { text: "hello", final: true },
    ]);
  });

  it("is purely reactive: a server-initiated close does not throw or retry", () => {
    const socket = new FakeSocket();
    const client = new WebSocketTranscriptResultsClient("ws://example/results", {
      createSocket: () => socket,
    });

    client.connect(() => {});
    socket.onclose?.();

    // No assertion needed beyond "doesn't throw" -- this class has no
    // timeout/retry logic of its own, per the agreed "server owns the
    // truth of when results are exhausted" rule.
    expect(socket.closed).toBe(false);
  });

  it("disconnect() closes the socket if still open", () => {
    const socket = new FakeSocket();
    const client = new WebSocketTranscriptResultsClient("ws://example/results", {
      createSocket: () => socket,
    });

    client.connect(() => {});
    client.disconnect();

    expect(socket.closed).toBe(true);
  });

  it("disconnect() is a no-op if already closed (e.g. by the server)", () => {
    const socket = new FakeSocket();
    const client = new WebSocketTranscriptResultsClient("ws://example/results", {
      createSocket: () => socket,
    });

    client.connect(() => {});
    socket.onclose?.();

    expect(() => client.disconnect()).not.toThrow();
  });
});
