---
beans_id: task-08a4e131
---
# 08: Silence Timeout & Navigation Stop

**What to build:** A Recording stops automatically after 15 seconds of no transcribed speech (Silence Timeout). Navigating away from the current Note view while Recording is active also stops and saves the Recording (Navigation Stop). Both behave identically to a manual Stop.

**Blocked by:** 03 (Record / Stop / Pause)

**Status:** ready-for-agent

- [ ] Silence Timeout: Recording stops automatically after 15 seconds of no transcribed speech during active Recording (not during Pause)
- [ ] Silence Timeout triggers the same stop-and-save behaviour as a manual Stop
- [ ] Navigation Stop: navigating away from the current Note view while Recording auto-triggers a stop-and-save
- [ ] Navigation Stop triggers the same stop-and-save behaviour as a manual Stop
- [ ] Silence Timeout timer resets whenever new transcribed speech arrives
