---
beans_id: task-e5dc0ca6
---
# 04: Transcription on Stop

**What to build:** When a Recording stops (via Stop, Silence Timeout, or Navigation Stop), captured audio is sent for transcription. The resulting text is inserted into the active Note's Text Content at the cursor position. The Note is auto-saved after transcription completes. This is the core value-delivery moment of the app.

**Blocked by:** 03 (Record / Stop / Pause)

**Status:** ready-for-agent

- [ ] Audio from a completed Recording is sent to the transcription service on Stop
- [ ] Transcribed text is inserted into the Note at the current cursor position, unstyled
- [ ] Note is auto-saved after transcription finishes
- [ ] Pause flushes the current audio buffer for transcription; Resume starts a new buffer
- [ ] Transcription errors surface a user-visible message; the Note is not corrupted
