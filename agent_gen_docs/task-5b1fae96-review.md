# Code Review — task-5b1fae96: Deliver streaming transcription results to the frontend

**Author:** agent (on behalf of hyouseff227@gmail.com)
**Date:** 2026-09-26
**Scope:** Backend results-delivery WebSocket + orchestrator wiring, frontend `TranscriptResultsClient`, batch-path `transcription` field wiring, merge-conflict cleanup in `main.py`.

## Summary

Implements the design agreed in the grilling session for ticket 13: a second,
dedicated WebSocket (`/api/recording/results`) delivers streaming
transcription results to the frontend, opened together with the audio
socket and closing only once a `final=true` result is forwarded. Audio
streaming is rejected outright if no results channel is attached
(precondition, not silently tolerated). The batch path's previously-dead
`result["transcription"]` field is now read and displayed on the frontend
for the first time. A pre-existing unresolved merge conflict in
`backend/app/main.py` was resolved as a prerequisite.

## What changed

### Backend
- **`backend/app/main.py`**: resolved merge conflict; added
  `/api/recording/results` WebSocket endpoint and `WebSocketResultsChannel`;
  `/api/recording/stream` now rejects (code `4410`) if no results channel is
  attached.
- **`backend/app/streaming_orchestrator.py`**: added `ResultsChannel`
  protocol, `attach_results_channel`/`detach_results_channel`/
  `has_results_channel`, and forwarding logic in `_consume()` that sends
  each result to the attached channel and detaches on `final=True`.
- **Tests added**: `test_streaming_orchestrator.py` (forwarding, detach-on-
  final, persistence across Pause/Resume, `has_results_channel`),
  `test_recording_results_ws.py` (connection-gating at the WS layer),
  `test_recording_stream_ws.py` updated for the new gating precondition.

### Frontend
- **`frontend/src/transcript-results-client.ts`** (new):
  `WebSocketTranscriptResultsClient`, a separate class (not bolted onto
  `RecordingClient`) that connects to the results socket and reflects
  `{text, final}` messages to a callback. Purely reactive — never closes
  proactively, no client-side timeout.
- **`frontend/src/recording-client.ts`**: added `BatchTranscriptionResult`
  and `transcription?` on `RecordingSnapshot`, wiring up the previously-dead
  field.
- **`frontend/src/recording-controls.ts`**: tracks `lastTranscription`,
  overwritten (not appended) on each Pause/Stop response.
- **Tests added**: `transcript-results-client.test.ts` (4 tests),
  `recording-controls.test.ts` additions (transcription overwrite behavior).

## Design decisions honored (from the grilling session)

| Decision | Implemented as |
|---|---|
| Second dedicated WebSocket | `/api/recording/results`, separate from `/api/recording/stream` |
| Open together with audio socket | Results socket must be attached before `/api/recording/stream` accepts (rejects with code `4410` otherwise) |
| Close only on `final=True` | `_consume()` detaches the channel only when a final result is forwarded; Pause/Stop with no pending final leaves it attached |
| Message shape | `{"text": str, "final": bool}` only |
| Frontend surface | Separate `WebSocketTranscriptResultsClient`, not on `RecordingClient` |
| Frontend close behavior | Purely reactive — no client timeout/retry |
| Batch path (`transcription` field) | Now read and displayed; overwrites, doesn't accumulate |
| Placeholder/fake location | `FakeResultsChannel`/`FakeStreamingSession` live only in test modules, following the existing `Protocol` + `Fake*` pattern |

## Notable implementation issue found and fixed during development

The first `WebSocketResultsChannel` design had `send()` (called from the
orchestrator's background consume task) call `websocket.close()` directly,
while a separate `wait_closed()` coroutine (in the request-handler task)
concurrently called `websocket.receive()` on the *same* socket. Two
coroutines driving one Starlette WebSocket concurrently deadlocked under
`TestClient`. Fixed by making the request-handler task the sole owner of
the socket (accept/send/receive/close all in one place), with the
orchestrator only ever touching an `asyncio.Queue`-backed `channel` object
that never touches the transport directly.

## Known test-suite limitation (documented, not fixed)

A live, two-concurrent-WebSocket integration test (audio + results socket
both open, exchanging real messages) was attempted but abandoned. It
requires both sockets — plus the POST that starts the orchestrator — to
share one `TestClient` portal/event loop (`with TestClient(app) as
client:`). Entering that shared portal binds process-wide singletons'
(`recording_session`, `audio_registry`, `silence_monitor`) event-loop-bound
internals (`asyncio.Lock`, `asyncio.Task`) to a loop that is torn down at
the end of the test, corrupting every *later* test module that relies on
the suite's default per-call throwaway-portal `TestClient` behavior
(observed as spurious `CancelledError` in unrelated modules).

This is scoped out rather than fixed: the orchestrator-level forwarding/
close-on-final/persists-across-pause behavior is already covered against a
fake channel in `test_streaming_orchestrator.py`, and the WS-layer
connection-gating precondition is covered without needing two live sockets.
The comment in `test_recording_results_ws.py` documents this explicitly for
future maintainers. **Follow-up suggestion:** if a live two-socket test is
needed later, consider running it in a subprocess/isolated test session so
its portal's loop-bound contamination can't leak into the rest of the
suite.

## Test results

- Backend: **51 passed** (`pytest backend/tests/ -q`)
- Frontend: **40 passed** across 5 files (`vitest run`)
- Backend typecheck: **mypy clean** (`mypy backend/app --ignore-missing-imports`)
- Frontend typecheck: changed files (`transcript-results-client.ts`,
  `recording-client.ts`, `recording-controls.ts`, `mic-stream.ts`) compile
  cleanly. `renderer.ts` has 6 pre-existing `TS5097` errors (`.ts` import
  extensions) unrelated to this change — not introduced or touched here.

## Follow-ups not in scope for this ticket (flagged during grilling, deliberately deferred)

- Batch path's dead `transcription` field was fixed here per Q2, but no
  actual Note-rendering UI exists yet to display `RecordingControls.transcription`
  — it's tracked and test-covered, but not yet painted into the DOM (no
  such region exists in `shell.ts`/`recording-controls.ts`'s `html()` yet).
- `renderer.ts` is not wired up to construct/connect a
  `WebSocketTranscriptResultsClient` yet — the class exists and is tested,
  but nothing in the app's bootstrap (`renderer.ts`) instantiates it
  alongside `MicWebSocketStreamer`. Wiring that up, plus a UI surface for
  live streamed text, is natural follow-on work once a real Note-rendering
  surface exists.
