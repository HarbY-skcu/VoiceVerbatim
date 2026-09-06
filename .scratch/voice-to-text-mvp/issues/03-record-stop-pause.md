---
beans_id: task-119c0c9d
---
# 03: Record / Stop / Pause

**What to build:** Users can click Record to begin capturing microphone audio from the selected Audio Source, Pause to stop the mic and enable editing (with Resume to restart capture at the cursor), and Stop to end the Recording session. The Recording lifecycle state machine is wired — no transcription yet, but audio is captured correctly.

**Blocked by:** 02 (Audio Source Selection)

**Status:** ready-for-agent

- [ ] Record button starts microphone capture; button state reflects active Recording
- [ ] Pause stops mic input immediately; Note text becomes editable; Silence Timeout does not apply during Pause
- [ ] Resume restarts mic capture; new transcription will insert at current cursor position
- [ ] Stop ends the Recording session; audio is ready for transcription (handed off, result discarded in this ticket)
- [ ] Only one Recording session can be active at a time
