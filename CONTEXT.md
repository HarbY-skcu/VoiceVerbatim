# Voice-to-Text Notes App

A desktop application that captures microphone audio, transcribes it into text, and lets users build a persistent, editable collection of notes. The core value proposition is removing typing friction from knowledge capture.

## Language

### Audio

**Recording**:
Transient audio captured from a microphone during a single capture session. Discarded immediately after transcription by default. Retained only when the user enables audio saving in Settings.
_Avoid_: Audio file, voice note, clip

**Audio Source**:
The microphone input device selected for a Recording. Chosen from a dropdown of OS-reported input devices; the system default is pre-selected.
_Avoid_: Input, microphone channel, audio device

**Audio Bank**:
A setting-gated list of (character position, audio file) pairs stored alongside a Note. Each entry marks where a transcription chunk was inserted into the Note's text. Only present when audio saving is enabled in Settings.
_Avoid_: Audio log, recording index

### Notes

**Note**:
The persisted document produced from one or more transcription passes. Composed of two independent layers: the **text content** (a flat string, the exportable substance of the note) and the **styling** (display metadata local to that note, not exported in MVP). Has a title (auto-generated on first save, then user-editable) and a creation timestamp.
_Avoid_: Document, transcript, file

**Note Title**:
A short label auto-generated from the first sentence of text content on first auto-save. If text content is less than a sentence at save time, a generic title is assigned ("untitled-1", "untitled-2", etc., incrementing globally). The title does not change automatically after initial assignment; only manual edits update it.
_Avoid_: Name, label, heading

**Text Content**:
The flat string of characters that constitutes a Note's substance. What gets exported. Transcription inserts into it at the cursor position; direct typing also modifies it. Styling has no effect on text content.
_Avoid_: Raw text, body, transcript

**Styling**:
Display metadata attached to a Note that controls visual presentation (font size, weight, alignment, highlight, underline). Stored locally per Note and applied at render time. Not exported in MVP; future exports will attempt to translate styling into the target file format.
_Avoid_: Formatting, markup, rich text

### Transcription

**Transcription**:
The process of converting audio from a Recording into text and inserting it into the active Note at the current cursor position. Triggered when a Recording stops (via Stop, Silence Timeout, or Navigation Stop) or when the buffer is flushed on Pause. New transcribed text arrives unstyled.
_Avoid_: Speech-to-text, recognition, conversion

**Pause**:
A Recording state in which microphone input stops immediately. The Note's text content becomes editable. On Resume, audio capture restarts and new transcription inserts at the current cursor position, intermixing with any edits made during the pause. A paused Recording stays paused indefinitely — Silence Timeout does not apply.
_Avoid_: Hold, suspend

**Record Correction**:
An action on a saved Note that starts a new Recording session against that Note. Creates a temporary Draft copy; new transcription inserts at the cursor position. On Stop, the Draft replaces the original Note. If no speech is produced, the Draft is discarded and the original Note is unchanged. This is the same action as "recording more" into an existing Note. The wireframe incorrectly shows this as two separate buttons ("Re-record section" and "Record correction") — there is only one action.
_Avoid_: Re-record section, record more, append recording

### Recording Lifecycle

**Silence Timeout**:
A 15-second threshold of no transcribed speech that automatically stops a Recording and triggers a save. Applies only during active Recording (not during Pause, when the mic is already off). Prevents background noise from keeping a Recording alive indefinitely.
_Avoid_: Inactivity timeout, silence detection

**Navigation Stop**:
Automatic stopping and saving of an active Recording when the user navigates away from the current Note view. Behaves identically to a manual Stop.
_Avoid_: Implicit stop, background stop

### Persistence

**Draft**:
The in-progress state of a Note during an active Recording. Auto-saved to a temporary location every 2–3 minutes. On Stop, the Draft is discarded and the Note is finalised. On crash, the most recent Draft auto-save is automatically promoted to a full Note, accessible in All Notes on next launch with no recovery prompt needed.
_Avoid_: Temp note, unsaved note, working note

**Auto-save**:
A background save triggered in two contexts: (1) periodically every 2–3 minutes during active Recording, writing to the Draft location; (2) after transcription finishes processing and after subsequent edits to a saved Note.
_Avoid_: Background save, implicit save

**Stop**:
The user action that ends a Recording. Always implicitly saves — there is no "Stop without saving." Discards the Draft temp file and finalises the Note. The wireframe label "Stop & Save" is misleading; the canonical term is Stop.
_Avoid_: Stop & Save, end recording

**Save**:
Persisting a Note in the app's internal format so it remains editable, searchable, and appendable via Record Correction. The implicit save on Stop and Auto-save both write to this format. The "Save" button in the edit view triggers this manually.
_Avoid_: Manual save, export, save as

**Export**:
Converting a Note's Text Content from the internal format into an external file format (plain text, PDF, Word document, etc.) for use outside the app. Styling is not included in MVP exports. Export formats beyond plain text are to be decided. Distinct from Save.
_Avoid_: Save as, download

### Organisation

**Bookmark**:
A star flag on a Note that causes it to appear in the Bookmarks tab in addition to All Notes. Does not remove it from All Notes.
_Avoid_: Star, favourite, pin

**All Notes**:
The primary sidebar view listing every saved Note, ordered by date last edited. Searchable by note title only. In-note full-text search is available via Ctrl+F from within an open Note. Does not filter by Bookmark status.
_Avoid_: Note list, library, archive

**Bookmarks**:
A sidebar nav item and view listing only Bookmarked Notes, ordered by date last edited. A Note appears in both All Notes and Bookmarks simultaneously.
_Avoid_: Starred notes, favourites, pinned notes
