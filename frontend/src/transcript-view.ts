/**
 * Ticket 14: assembles and displays the growing note body in real time as
 * streaming transcription results arrive, and owns the Note's cursor --
 * composition/positioning ownership moved to the frontend entirely. The
 * backend only ever sources transcribed text (streaming interim/final
 * results, batch results); this class decides where that text lands.
 *
 * Final (committed) text is spliced in at `cursor`, not appended at the
 * end -- a user who Stops, clicks mid-text, then Records again gets new
 * speech inserted at that clicked position, with everything after it
 * pushed along. Interim words appear greyed out and italic inline at
 * the cursor, replaced (not appended to) on each revision until a final
 * result commits them into the plain-text run and advances the cursor
 * past just what was inserted.
 *
 * Read-only while recording; editable only once fully stopped (idle) --
 * per ticket 14, cursor repositioning is only meaningful then.
 * Manual edits made while editable also feed back into the tracked
 * text/cursor, debounced (~2s) before being reported via `onTextChanged`;
 * transcription results report immediately (no debounce). Auto-scrolls
 * to the bottom on every applied result so the latest text stays in view.
 */

const MANUAL_EDIT_DEBOUNCE_MS = 2000;

export interface TranscriptResultLike {
  text: string;
  final: boolean;
}

export interface TranscriptViewDeps {
  /**
   * Called whenever the composed text changes and should be persisted
   * to the backend (full-text overwrite, `PUT /api/note`). `immediate`
   * is true for transcription results and forced flushes, false for a
   * debounced manual-edit save.
   */
  onTextChanged?(text: string, immediate: boolean): void;
}

export class TranscriptView {
  private text = "";
  private cursor = 0;
  private interimText = "";
  private readonly titleEl: HTMLElement;
  private readonly bodyEl: HTMLElement;
  private debounceTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private readonly root: HTMLElement,
    private readonly deps: TranscriptViewDeps = {}
  ) {
    this.root.innerHTML = `
      <div data-region="note-title"></div>
      <div data-region="note-body" contenteditable="false"></div>
    `;
    this.titleEl = this.root.querySelector('[data-region="note-title"]') as HTMLElement;
    this.bodyEl = this.root.querySelector('[data-region="note-body"]') as HTMLElement;

    // Only meaningful while editable (contenteditable="true"); clicking or
    // typing in a read-only contenteditable region doesn't fire these in
    // a way that matters here, so no extra guard is needed on top of the
    // attribute itself.
    this.bodyEl.addEventListener("click", () => this.syncCursorFromSelection());
    this.bodyEl.addEventListener("input", () => this.handleManualEdit());
  }

  setTitle(title: string): void {
    this.titleEl.textContent = title;
  }

  /** Read-only while recording; editable only once idle (ticket 14). */
  setReadOnly(readOnly: boolean): void {
    this.bodyEl.setAttribute("contenteditable", readOnly ? "false" : "true");
  }

  /** The current composed text (committed; excludes any open interim span). */
  getText(): string {
    return this.text;
  }

  /** The current insertion cursor -- exposed mainly for tests/diagnostics. */
  getCursor(): number {
    return this.cursor;
  }

  /**
   * Explicitly positions the cursor. Production callers reach this via a
   * click in the editable body (`syncCursorFromSelection`); exposed
   * directly too since it's the real seam under test, independent of
   * jsdom's limited `Selection`/`Range` support.
   */
  setCursor(index: number): void {
    this.cursor = Math.max(0, Math.min(index, this.text.length));
  }

  /**
   * Applies one streaming or batch result. Interim results replace the
   * previous interim run (the speech engine revising its guess) and are
   * shown inline at the cursor without being committed. A final result
   * splices its text into the committed text at the cursor -- not at the
   * end -- and advances the cursor to just past what was inserted, so a
   * following result continues from there rather than overwriting
   * already-committed text elsewhere in the note.
   */
  applyResult(result: TranscriptResultLike): void {
    if (result.final) {
      this.text = this.text.slice(0, this.cursor) + result.text + this.text.slice(this.cursor);
      this.cursor += result.text.length;
      this.interimText = "";
      this.paint();
      this.scrollToBottom();
      this.deps.onTextChanged?.(this.text, true);
    } else {
      this.interimText = result.text;
      this.paint();
      this.scrollToBottom();
    }
  }

  /** Forces any pending debounced manual-edit save through immediately. */
  flushPendingEdits(): void {
    if (this.debounceTimer === null) {
      return;
    }
    clearTimeout(this.debounceTimer);
    this.debounceTimer = null;
    this.deps.onTextChanged?.(this.text, true);
  }

  private paint(): void {
    this.bodyEl.textContent = "";
    const before = this.text.slice(0, this.cursor);
    const after = this.text.slice(this.cursor);
    if (before) {
      this.bodyEl.appendChild(document.createTextNode(before));
    }
    if (this.interimText) {
      const span = document.createElement("span");
      span.className = "interim";
      span.textContent = this.interimText;
      this.bodyEl.appendChild(span);
    }
    if (after) {
      this.bodyEl.appendChild(document.createTextNode(after));
    }
  }

  /** Reads the DOM caret position (set by a click) back into `cursor`. */
  private syncCursorFromSelection(): void {
    const selection = window.getSelection?.();
    if (!selection || selection.rangeCount === 0) {
      return;
    }
    const range = selection.getRangeAt(0);
    if (!this.bodyEl.contains(range.startContainer)) {
      return;
    }
    this.cursor = this.offsetWithin(range.startContainer, range.startOffset);
  }

  /** Converts a (node, offset) DOM position into a plain-text character offset within `bodyEl`. */
  private offsetWithin(node: Node, nodeOffset: number): number {
    const walker = document.createTreeWalker(this.bodyEl, NodeFilter.SHOW_TEXT);
    let offset = 0;
    let current = walker.nextNode();
    while (current !== null) {
      if (current === node) {
        return offset + nodeOffset;
      }
      offset += current.textContent?.length ?? 0;
      current = walker.nextNode();
    }
    // node wasn't a text node under bodyEl (e.g. bodyEl itself, when the
    // click landed on empty space) -- clamp to the end of the text.
    return this.text.length;
  }

  /**
   * Reconciles a manual edit (typing/deleting while editable) back into
   * the tracked text, and schedules a debounced save. There is no
   * interim span while editable, so the DOM's plain text is simply the
   * new committed text.
   */
  private handleManualEdit(): void {
    this.text = this.bodyEl.textContent ?? "";
    this.syncCursorFromSelection();
    this.scheduleDebouncedSave();
  }

  private scheduleDebouncedSave(): void {
    if (this.debounceTimer !== null) {
      clearTimeout(this.debounceTimer);
    }
    this.debounceTimer = setTimeout(() => {
      this.debounceTimer = null;
      this.deps.onTextChanged?.(this.text, false);
    }, MANUAL_EDIT_DEBOUNCE_MS);
  }

  private scrollToBottom(): void {
    this.bodyEl.scrollTop = this.bodyEl.scrollHeight;
  }
}
