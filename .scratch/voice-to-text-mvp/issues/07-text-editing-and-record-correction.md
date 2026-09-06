---
beans_id: task-acac338d
---
# 07: Text Editing & Record Correction

**What to build:** Users can click into any saved Note and type to edit its Text Content directly. The Record Correction action starts a new Recording session on an existing Note — new transcription inserts at the cursor position. If no speech is produced, the Draft is discarded and the original Note is unchanged. Auto-save fires after edits settle.

**Blocked by:** 05 (Note Persistence & All Notes View)

**Status:** ready-for-agent

- [ ] Clicking into a saved Note's text area enables direct typing; changes update Text Content
- [ ] Auto-save fires after transcription finishes and after subsequent direct edits
- [ ] Record Correction starts a new Recording session on the open Note, creating a temporary Draft
- [ ] On Stop, the Draft replaces the original Note if any transcription was produced
- [ ] If no speech is produced during a Record Correction session, Draft is discarded and the original Note is unchanged
- [ ] Record Correction is a single action (not separate "re-record section" and "record more" buttons)
