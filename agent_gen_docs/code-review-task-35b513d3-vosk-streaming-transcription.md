# Code Review — Ticket 12 (`task-35b513d3`): Local Vosk speech-to-text backend

**Scope:** diff against the pre-implementation state of this worktree (`backend/` only; `frontend/`/`node_modules` changes in the working tree are unrelated noise from environment setup, not reviewed here).

**Commits:** uncommitted working-tree changes (not yet committed).

## Standards

No `CODING_STANDARDS.md`/`CONTRIBUTING.md` exists in this repo, so this axis is the Fowler smell baseline only, applied as judgement calls.

- **Mysterious Name** — none spotted. `FfmpegTranscoder`, `VoskRecognizer`, `VoskStreamingTranscriptionSession` all say what they are.
- **Divergent Change** — `backend/app/main.py`'s diff mixes two unrelated concerns: resolving stale merge-conflict markers *and* retiring the batch path/wiring the new service. This was a deliberate, agreed order (conflict resolution first, per the grilling session), but as landed in one file it's still two reasons to touch the file. Judgement call, not a hard violation — acceptable given the explicit sequencing decision, but worth a mental note if this gets split into commits (resolve conflicts as commit 1, wire Vosk as commit 2).
- **Primitive Obsession** — `VoskStreamingTranscriptionService.model_path: str = DEFAULT_MODEL_PATH` is a bare string standing in for "a location on disk that must exist and be a valid Vosk model." Minor; a `Path` type would be marginally more honest but this is a judgement call, not worth blocking on.
- **Speculative Generality** — `Transcoder`/`Recognizer` `Protocol`s are new abstraction introduced ahead of a second real implementation ever existing. This is *not* flagged as a smell here: the grilling session explicitly settled on injectable seams so `vosk_transcription.py` is testable without a real model file/ffmpeg binary in this sandboxed environment, and the resulting tests (`test_vosk_transcription.py`) exercise real behavior through fakes rather than tautologically. The abstraction earns its keep via testability, not "future-proofing."
- **Duplicated Code** — none found; `_read_available`'s timeout-based drain loop is unique to `FfmpegTranscoder` and isn't duplicated elsewhere.
- **Message Chains / Middle Man** — none.
- One real gap: `FfmpegTranscoder._read_available` polls `stdout.read(4096)` with a hardcoded `0.01`s timeout in a loop — a magic number with no named constant or comment justifying `0.01` specifically. Worth a named constant (`_POLL_TIMEOUT_SECONDS`) or at least a comment on why that value was chosen, since it directly affects streaming latency/CPU usage trade-off.

## Spec

Cross-referenced against the grilling-session transcript (the closest thing to a spec here) and the original bean body (`task-35b513d3`).

**Implemented as specified:**
- Local, fully-offline Vosk backend (no hosted API, no credentials) — ✅ `vosk_transcription.py` only calls `vosk.Model`/`vosk.KaldiRecognizer` locally.
- No separate batch path — ✅ `TranscriptionService`, `TranscriptionPipeline`, `UnconfiguredTranscriptionService`, `/api/recording/audio-chunk`, and their tests are all deleted; `main.py`'s `pause`/`stop`/`navigation_stop` no longer call `flush_and_transcribe()`.
- Variable-size chunk-in/text-out loop, no manual re-buffering — ✅ `VoskStreamingTranscriptionSession.send_audio` feeds whatever `Transcoder.feed()` decodes straight into `accept_waveform()`, one call per `send_audio()` invocation.
- `final=True` driven by Vosk's own endpoint detection, not by `close()` — ✅ `send_audio` sets `final=True` only when `accept_waveform()` returns truthy (an endpoint), matching "use Vosk's own `Result()` endpoint detection."
- ffmpeg-based transcoding (not a pure-Python decoder) — ✅ `FfmpegTranscoder` shells out to `ffmpeg` via `asyncio.create_subprocess_exec`.
- Force-finalize trailing partial utterance on session close — ✅ `close()` flushes the transcoder, feeds remaining PCM, then calls `recognizer.final_result()` and emits it as `final=True` if non-empty.
- `main.py` merge conflicts resolved first, as agreed — ✅ all 6 conflict-marker blocks removed; behavior consolidated onto the Feature-4.1 (streaming-only) side.
- Model download via gitignored `backend/models/` + setup script — ✅ `backend/scripts/download_model.sh` + `.gitignore` entry added.

**Gaps / concerns:**
- **"Live Note updates … replacing the tail" (grilling round 4, Q2)** is implemented entirely inside the pre-existing `ActiveNote.insert_streaming` (unchanged) and `StreamingTranscriptionOrchestrator._consume` (unchanged) — correct, but worth noting explicitly that *no new code* was needed here; this ticket's own scope didn't require touching those files, which matches "nothing else in the system needs to change" for that specific mechanism.
- **`FfmpegTranscoder`/`VoskRecognizer`/`_load_model` are entirely unexercised by the test suite** — no test imports the real `ffmpeg` subprocess path or a real `vosk.Model`, because neither is available in the sandbox this was built in (confirmed: no `ffmpeg` binary, no root to `apt-get install` it). `test_vosk_transcription.py` only covers `VoskStreamingTranscriptionSession` against `Transcoder`/`Recognizer` fakes. **This means the actual "does ffmpeg correctly decode a real browser WebM/Opus blob into PCM Vosk accepts" question — the concrete verification the grilling session agreed to do ("yes — verify with a quick real test... rather than assuming from documentation alone") — has not actually been performed.** This is a spec commitment made and not yet honored; flagging as the most important open item.
- **No `backend/models/vosk-model-en-us-0.22` model is present**, and `download_model.sh` itself is untested (never run) — reasonable given no network/root access in this environment, but means `VoskStreamingTranscriptionService` has never been exercised against a real model end-to-end.
- Ticket text also says "Must also settle the audio payload contract... and what/whether transcoding is needed" — settled and implemented, but the specific *sample rate/format assumption* (WebM/Opus in, 16kHz mono PCM16 out) is only asserted via the `ffmpeg` command-line flags, never verified against what `MicWebSocketStreamer`/`MediaRecorder` on the frontend actually emit (browser/codec-dependent, per the ticket's own caveat). No test or comment cross-checks this against the actual frontend recorder config.

## Summary

- **Standards:** 1 finding (magic timeout constant), all others judgement calls / no violations. Worst: the unnamed `0.01`s poll timeout in `FfmpegTranscoder`.
- **Spec:** 8 requirements matched, 3 concerns. Worst: the agreed real-audio verification against actual ffmpeg + Vosk was never performed (blocked by sandbox environment lacking `ffmpeg`/model/network access) — the implementation is currently verified only against fakes, not against a real decode-and-transcribe round trip.
