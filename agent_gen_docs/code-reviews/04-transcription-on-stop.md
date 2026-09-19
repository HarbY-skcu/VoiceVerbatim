# Code Review — Ticket 04: Transcription on Stop

**Beans ID:** `task-e5dc0ca6`
**Files:** `backend/app/audio_buffer.py`, `backend/app/note.py`, `backend/app/transcription.py`, `backend/app/transcription_pipeline.py`, `backend/app/main.py`, `backend/tests/test_transcription_pipeline.py`, `backend/tests/test_recording_transcription.py`, `backend/tests/test_recording.py` (updated), `pytest.ini` (new)
**Tests:** 30 backend passing (25 frontend unchanged, untouched by this ticket)

---

## What was built

The core value-delivery pipeline: audio captured during a Recording is flushed and sent for transcription when the Recording stops (or pauses), the resulting text is inserted into the active Note at the cursor position, and the Note is auto-saved. Transcription failures surface as a structured error without touching the Note's existing content.

No Note editor UI exists yet (title/text-content editing is tickets 06/07), so this ticket is entirely backend: a pipeline seam that a future editor and future real audio wiring (ticket 04.1) can both plug into.

---

## TDD process

Red → green, seam by seam:

1. Wrote `test_transcription_pipeline.py` first, against four collaborators that didn't exist yet (`AudioBuffer`, `ActiveNote`, `TranscriptionService`, `TranscriptionPipeline`) — confirmed the import failed.
2. Implemented each collaborator as a small, single-purpose unit:
   - `AudioBuffer` — accumulates raw chunks, `flush()` returns and clears them.
   - `ActiveNote` — minimal in-memory Note stand-in (`insert_at_cursor`, `save`) until ticket 05 lands real persistence.
   - `TranscriptionService` (a `Protocol`) + `TranscriptionError` — the seam a real speech-to-text backend will implement later.
   - `TranscriptionPipeline` — flush → transcribe → insert → save, with the flush happening *before* the transcribe call so the buffer is cleared even if transcription fails (this is what makes "Resume starts a new buffer" hold regardless of the previous attempt's outcome).
   Ran the single test file → green (6 tests).
3. Wrote `test_recording_transcription.py` next, exercising the same pipeline through HTTP (`/api/recording/audio-chunk`, and transcription-on-`stop`/`pause`) using a `FakeTranscriptionService` — confirmed it failed (no `note`/`pipeline` module-level instances in `main.py` yet).
4. Wired `main.py`: added `AudioChunkIn`, the `/api/recording/audio-chunk` endpoint, and extended the shared `_transition()` helper with an optional `with_transcription` flag so `stop` and `pause` both flush-and-transcribe while `start`/`resume` don't. Ran the single test file → green (6 tests).
5. Updated the three pre-existing `test_recording.py` assertions that now also receive a `transcription` key in the response body (pause/stop responses changed shape) — this was an intentional, expected break, not an accidental regression.
6. Ran the full backend suite once — 30 passed. Ran frontend typecheck/tests once — unchanged, pre-existing `TS5097` warnings only (same ones noted in ticket 03's review; no frontend files touched by this ticket).

---

## Design

**`AudioBuffer`** is deliberately dumb — it doesn't know about transcription, the Recording state machine, or the Note. It only accumulates bytes and clears itself on `flush()`. This keeps "Resume starts a new buffer" a property of one method's contract rather than something callers have to remember to do separately.

**`ActiveNote`** is an explicit placeholder, not a shortcut: it's the same seam ticket 05 (Note Persistence) will replace with real storage. Ticket 04 needs *somewhere* to insert text and observe a save happened; it doesn't need file I/O, so it uses the smallest thing that satisfies the acceptance criteria without pretending to solve a later ticket's problem.

**`TranscriptionService` as a `Protocol`** keeps the pipeline testable without a real STT integration. `main.py` wires an `UnconfiguredTranscriptionService` by default that raises `TranscriptionError` — an honest placeholder (surfaces a clear error) rather than a silent no-op, until ticket 04.1's real streaming pipeline replaces it.

**`TranscriptionPipeline.flush_and_transcribe()`** is the single seam Stop, Pause, Silence Timeout (ticket 08), and Navigation Stop (ticket 08) can all call identically — matching the ticket's explicit requirement that Pause behaves the same as Stop for buffer flushing. `main.py`'s `_transition()` helper gained a `with_transcription` flag rather than duplicating the flush-transcribe-insert-save sequence at each of the four endpoints.

**Error handling:** `flush_and_transcribe()` catches `TranscriptionError` internally and returns `{"inserted": None, "error": <message>}` rather than raising — this is what "the Note is not corrupted" means in practice: the buffer is already flushed (cleared) by the time transcription is attempted, but `note.insert_at_cursor()` and `note.save()` are never called on failure, so the Note's existing text and last-saved state are untouched.

---

## Acceptance criteria coverage

| Criterion | Covered by |
|---|---|
| Audio from a completed Recording is sent to the transcription service on Stop | `/api/recording/stop` → `with_transcription=True` → `pipeline.flush_and_transcribe()` |
| Transcribed text is inserted into the Note at the current cursor position, unstyled | `ActiveNote.insert_at_cursor` (plain string splice, no styling data touched) |
| Note is auto-saved after transcription finishes | `pipeline.flush_and_transcribe()` calls `note.save()` only on success |
| Pause flushes the current audio buffer for transcription; Resume starts a new buffer | `/api/recording/pause` also sets `with_transcription=True`; `AudioBuffer.flush()` clears on every call, verified by `test_resume_starts_a_new_buffer_after_pause_flushed_it` |
| Transcription errors surface a user-visible message; the Note is not corrupted | `TranscriptionError` caught in the pipeline, returned as `{"error": <message>}`; `test_transcription_error_on_stop_surfaces_without_corrupting_the_note` asserts `note.text` and `note.saved_text` are unchanged |

---

## Deferred

| Concern | Reason |
|---|---|
| Real speech-to-text integration | Ticket 04.1 (Real-time streaming audio capture & transcription pipeline) — `UnconfiguredTranscriptionService` is the placeholder it will replace |
| Real Note persistence (multiple notes, titles, disk storage) | Ticket 05 — `ActiveNote` is a single in-memory placeholder |
| Note editor UI (cursor position driven by real user input, styling) | Tickets 06/07 — no frontend changes were made in this ticket |
| Silence Timeout / Navigation Stop calling the pipeline | Ticket 08 — the pipeline's shape (`flush_and_transcribe()`) is what those call sites will use, but the timers/navigation hooks don't exist yet |
| User-visible surfacing of the `transcription.error` field in the UI | No toolbar/editor exists yet to display it; the API already returns it in the response body for a future frontend to render |
