---
beans_id: task-473ae85a
---
# 02: Audio Source Selection

**What to build:** A dropdown in the recording toolbar lists all OS-reported input devices, with the system default pre-selected. Selecting a different device updates the active Audio Source for the next Recording. No recording yet — just device enumeration and selection UI.

**Blocked by:** 01 (Shell & Navigation Frame)

**Status:** ready-for-agent

- [ ] Dropdown enumerates all OS microphone input devices on app start
- [ ] System default device is pre-selected
- [ ] Selecting a device from the dropdown changes the active Audio Source
- [ ] Selection persists while the app is open (does not need to survive restart in this ticket)
