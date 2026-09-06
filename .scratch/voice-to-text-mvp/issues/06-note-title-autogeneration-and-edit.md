---
beans_id: task-9312e7a5
---
# 06: Note Title Auto-generation & Manual Edit

**What to build:** On first save, the app auto-generates a Note Title from the first sentence of Text Content, or assigns "untitled-N" (globally incrementing) if the content is too short. Users can click the title to edit it. The title does not change automatically after initial assignment — only manual edits update it.

**Blocked by:** 05 (Note Persistence & All Notes View)

**Status:** ready-for-agent

- [ ] First save generates a title from the first sentence of Text Content
- [ ] If Text Content is less than a sentence at save time, title is "untitled-1", "untitled-2", etc., incrementing globally across all Notes
- [ ] Title is displayed prominently in the main pane and in the All Notes sidebar entry
- [ ] Clicking the title in the main pane makes it editable inline
- [ ] Saving a manual title edit persists the change; auto-generation does not overwrite it later
