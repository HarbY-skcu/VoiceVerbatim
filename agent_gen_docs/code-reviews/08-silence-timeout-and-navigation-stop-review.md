# Code Review: 08 — Silence Timeout & Navigation Stop

**Bean:** `task-08a4e131`
**Reviewer/Author:** agent (Claude, via TDD)
**Status:** All acceptance criteria implemented and tested.

## Summary

Implements two automatic stop-and-save triggers, both required to behave
identically to a manual Stop:

- **Silence Timeout** — a Recording auto-stops after 15s with no transcribed
  speech, only while actively recording (not while paused).
- **Navigation Stop** — leaving the current Note view (e.g. switching sidebar
  tabs) auto-stops and saves an active Recording.

## What changed

### Backend

- **`backend/app/silence_timeout.py`** (new) — `SilenceTimeoutMonitor`. A
  small, independently testable class that owns an asyncio background task
  polling for silence. Takes `on_timeout`, `timeout_seconds`, `poll_interval`,
  and `clock` as constructor params — the injectable clock and poll interval
  let tests fire real timeouts in milliseconds instead of waiting 15
  real-world seconds. Public surface: `start()`, `notify_speech()`,
  `cancel()`, `is_running`.
- **`backend/app/main.py`**:
  - Instantiates one `silence_monitor` bound to `recording_session.stop`.
  - `start`/`resume` call `silence_monitor.start()`; `pause`/`stop` call
    `silence_monitor.cancel()` (Pause: mic is off, timeout doesn't apply per
    spec).
  - New `POST /api/recording/speech` — resets the silence window; the
    transcription pipeline is expected to call this whenever text arrives.
  - New `POST /api/recording/navigation-stop` — identical to manual Stop,
    except it's a no-op (200, unchanged state) when already idle, since
    navigating away with nothing running isn't an error condition.
- **`backend/pytest.ini`** (new) — `asyncio_mode = auto`, needed once
  `pytest-asyncio` tests were introduced for the monitor's background task.

### Frontend

- **`frontend/src/recording-client.ts`** — added `notifySpeech()` and
  `navigationStop()` to the `RecordingClient` interface and its HTTP
  implementation.
- **`frontend/src/shell.ts`** — `Shell` now takes an optional
  `NavigationStopNotifier` (deliberately a minimal one-method interface
  rather than the full `RecordingClient`, to avoid coupling the shell to
  recording concerns it doesn't otherwise need). Tab-switch handler calls
  `navigationStop()` when switching to a *different* tab; clicking the
  already-active tab is a no-op (no spurious stop calls).
- **`frontend/src/renderer.ts`** — wires a single shared
  `HttpRecordingClient` into both `Shell` (for Navigation Stop) and
  `RecordingControls` (for the toolbar), so both see the same backend state.

## Tests added

- `backend/tests/test_silence_timeout.py` — 4 tests on `SilenceTimeoutMonitor`
  in isolation (fires after timeout; `notify_speech` resets the window;
  `cancel` prevents firing; `start` is idempotent/restarts the window). Uses
  a `FakeClock` so timing is deterministic and fast.
- `frontend/tests/shell.test.ts` — 2 new tests: navigation-stop fires on a
  real tab switch, and does *not* fire when re-clicking the active tab.
- `frontend/tests/recording-controls.test.ts` — `FakeRecordingClient` extended
  with `notifySpeech`/`navigationStop` so it still satisfies the
  `RecordingClient` interface (no behavioral test changes needed there beyond
  compiling).
- Existing `backend/tests/test_recording.py` updated only to reset
  `silence_monitor` between tests (avoids a stray background task leaking
  across test cases).

No tests exist yet for wiring `notifySpeech()` into the actual
transcription pipeline, since that pipeline (bean 04) doesn't exist in this
codebase yet — see Gaps below.

## Design notes / rationale

- Kept the Silence Timeout mechanism entirely inside the backend, consistent
  with the existing pattern where the backend is the sole authority on
  Recording state (see `recording.py`'s docstring) — the frontend never
  decides transitions, only requests them and displays results.
- `SilenceTimeoutMonitor` is deliberately decoupled from `RecordingSession`:
  it doesn't know what "recording" means, it just calls a callback after a
  silence gap. This kept it unit-testable without spinning up FastAPI/asyncio
  session locks, and makes it reusable if another silence-triggered behavior
  is ever needed.
- `navigation-stop` is idempotent/no-op when idle rather than raising a 409,
  because "user navigated away, nothing was recording" is an expected event,
  not an error — unlike a manual Stop request while idle, which *should* be
  rejected (a user pressing Stop with nothing running is a bug in the UI).

## Known gaps / follow-ups

1. **No caller currently invokes `POST /api/recording/speech`.** The ticket
   states the timer resets "whenever new transcribed speech arrives," but
   this codebase has no transcription pipeline yet (see beans 04 / 04.1,
   both still open). The endpoint and monitor plumbing are ready; whoever
   implements streaming transcription needs to call `notifySpeech()` on each
   chunk.
2. **Navigation Stop is only wired to the sidebar tab switcher.** If future
   work adds other forms of "leaving the current Note view" (e.g. opening a
   specific note from a list, closing the app), those call sites will need
   to invoke `navigationStop()` too — `Shell` only covers the one navigation
   path that exists today.
3. `SilenceTimeoutMonitor.poll_interval` defaults to 0.5s against a 15s
   timeout — acceptable granularity for a save trigger, not reconsidered for
   the frontend/network requirements of the future streaming pipeline (bean
   04.1) which may want a tighter loop.

## Test results

- Backend: `22 passed` (`python3 -m pytest backend/tests -q`)
- Frontend: `21 passed` (`vitest run`, 3 files)
- `tsc --noEmit` reports pre-existing `TS5097` errors on `.ts`-suffixed
  imports across the whole `frontend/src` tree (present before this change,
  unrelated to this ticket — Vite/Vitest resolve these fine; only raw `tsc`
  without `allowImportingTsExtensions` complains). Not fixed here as out of
  scope for bean 08.
