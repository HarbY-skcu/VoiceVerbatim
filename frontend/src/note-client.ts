/**
 * Ticket 14: fetches/pushes the active Note (title + text) against the
 * backend's /api/note. Ticket 14's cursor-ownership rework moved
 * composition/positioning to the frontend entirely: the backend no
 * longer tracks or returns a cursor, it's just a sink for whatever full
 * text the frontend pushes via `updateActiveNote` (used for both the
 * debounced manual-edit save and the immediate transcription-result
 * save -- see TranscriptView/renderer.ts).
 */

export interface ActiveNoteSnapshot {
  title: string | null;
  text: string;
}

export interface NoteClient {
  getActiveNote(): Promise<ActiveNoteSnapshot>;
  /** Full-text overwrite: the frontend is the sole authority on composition/positioning. */
  updateActiveNote(text: string): Promise<ActiveNoteSnapshot>;
}

const DEFAULT_BASE_URL = "http://127.0.0.1:8000";

export class HttpNoteClient implements NoteClient {
  constructor(private readonly baseUrl: string = DEFAULT_BASE_URL) {}

  async getActiveNote(): Promise<ActiveNoteSnapshot> {
    const response = await fetch(`${this.baseUrl}/api/note`);
    return (await response.json()) as ActiveNoteSnapshot;
  }

  async updateActiveNote(text: string): Promise<ActiveNoteSnapshot> {
    const response = await fetch(`${this.baseUrl}/api/note`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    return (await response.json()) as ActiveNoteSnapshot;
  }
}
