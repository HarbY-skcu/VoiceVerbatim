# Code Review — Ticket 03: Record / Stop / Pause

**Beans ID:** `task-119c0c9d`
**Files:** `backend/app/recording.py`, `backend/app/main.py`, `backend/tests/test_recording.py`, `frontend/src/recording-client.ts`, `frontend/src/recording-controls.ts`, `frontend/tests/recording-controls.test.ts`, `frontend/src/renderer.ts`
**Tests:** 10 backend + 7 frontend passing (18 backend / 25 frontend total in full suite)

---

## What was built

The Recording lifecycle state machine described in ticket 03: `idle → recording → paused → recording → idle`, wired end-to-end from a Record/Pause/Resume/Stop toolbar down to a backend-owned state machine. No audio capture or transcription — only the lifecycle state, matching the ticket's scope ("audio is captured correctly" is deferred to real mic wiring; this ticket wires the state transitions).

Followed the same ownership pattern established in ticket 02 (Audio Source Selection): **the backend is the single source of truth**, and the frontend is a display layer that asks for a transition and renders whatever the backend reports.

---

## TDD process

Red → green, one seam at a time:

1. Wrote `backend/tests/test_recording.py` first (10 tests covering idle/start/pause/resume/stop and every illegal transition) — confirmed it failed on import (`recording_session` didn't exist).
2. Implemented `backend/app/recording.py` (`RecordingSession`) and wired 5 endpoints (`GET /api/recording`, `POST /api/recording/{start,pause,resume,stop}`) into `main.py` — ran the single test file, went green.
3. Wrote `frontend/tests/recording-controls.test.ts` first (7 tests using a `FakeRecordingClient` that can simulate both successful transitions and backend rejections) — confirmed it failed (module didn't exist).
4. Implemented `frontend/src/recording-client.ts` (`HttpRecordingClient`, mirrors `audio-source-client.ts`) and `frontend/src/recording-controls.ts` (`RecordingControls`) — ran the single test file, went green.
5. Wired `RecordingControls` into `renderer.ts` alongside the existing `AudioSourceSelector`, each in its own toolbar sub-region.
6. Ran type checking (`tsc --noEmit`) — the only errors are pre-existing `TS5097` warnings in `renderer.ts`'s original imports, unrelated to this change (present before any edits).
7. Ran the full backend (`pytest`) and frontend (`vitest`) suites once at the end — 18 and 25 tests passing respectively.

---

## Design

**Backend (`recording.py`):** `RecordingSession` is a tiny state machine with one field (`_state: str`). Each transition method validates the current state and raises `InvalidRecordingTransition` on an illegal move (e.g., `pause()` from `idle`). `main.py` catches that exception once, in a shared `_transition()` helper, and converts it to `409 Conflict` — avoiding four near-identical try/except blocks.

**Frontend (`recording-controls.ts`):** `RecordingControls` holds only the last state it was told about. On every button click it calls the corresponding `RecordingClient` method; on success it adopts the returned state, on `RecordingRejected` (409) it discards the attempt and repaints the state unchanged — the same "backend overrides the UI" behavior tested in ticket 02's audio selector. `isTextEditable` reflects ticket 03's requirement that "Pause... Note text becomes editable" (true whenever not actively recording).

**Only one active Recording:** enforced entirely on the backend — `start()` rejects unless `_state == "idle"`, so a second `start` while already recording is a `409`, exactly as the ticket's acceptance criterion specifies.

**Silence Timeout not applying during Pause:** out of scope for this ticket (no timer exists yet — that's ticket 08), but the state machine's shape (pause is a distinct state from recording) is what a future Silence Timeout will need to check against.

---

## Acceptance criteria coverage

| Criterion | Covered by |
|---|---|
| Record button starts capture; button state reflects active Recording | `RecordingControls` swaps Record → Pause/Stop; backend `POST /start` |
| Pause stops mic immediately; text becomes editable | `pause()` transition; `isTextEditable` getter |
| Resume restarts capture at cursor | `resume()` transition (cursor-position insertion itself belongs to ticket 04/07's text editing) |
| Stop ends the session; audio handed off for transcription | `stop()` transition returns to idle (transcription hookup is ticket 04, explicitly out of scope here) |
| Only one Recording active at a time | Backend rejects `start` unless idle (409) |

---

## Deferred

| Concern | Reason |
|---|---|
| Actual microphone capture (`getUserMedia`) | Not required by this ticket's stated scope; state machine is what's being wired |
| Transcription on Stop | Ticket 04 |
| Silence Timeout | Ticket 08 |
| Cursor-position text insertion | Tickets 04/07 |
