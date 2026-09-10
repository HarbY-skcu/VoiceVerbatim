export interface AudioSourceSnapshot {
  /** Every device the backend currently knows about, in display order. */
  sources: { id: string; label: string }[];
  /** The device the backend has selected for the next Recording, if any. */
  active: string | null;
}

/**
 * The backend owns which Audio Source is selected. This is the frontend's view
 * of that ownership: it hands the backend the OS device list and asks the
 * backend to change the selection. It never decides the default or validates a
 * choice itself.
 */
export interface AudioSourceClient {
  registerSources(
    sources: { id: string; label: string }[]
  ): Promise<AudioSourceSnapshot>;
  setActive(id: string): Promise<AudioSourceSnapshot>;
}

type DeviceEnumerator = () => Promise<MediaDeviceInfo[]>;

/**
 * Renders the Audio Source dropdown. Enumeration of OS input devices happens
 * here (a browser-only capability); every selection decision is delegated to the
 * backend and this component only displays the result.
 */
export class AudioSourceSelector {
  private snapshot: AudioSourceSnapshot = { sources: [], active: null };

  constructor(
    private readonly root: HTMLElement,
    private readonly client: AudioSourceClient,
    private readonly enumerateDevices: DeviceEnumerator = () =>
      navigator.mediaDevices.enumerateDevices()
  ) {}

  async render(): Promise<void> {
    const all = await this.enumerateDevices();
    const inputs = all
      .filter((d) => d.kind === "audioinput")
      .map((d) => ({ id: d.deviceId, label: d.label }));

    this.snapshot = await this.client.registerSources(inputs);
    this.paint();
  }

  /** The Audio Source the backend has selected, as last reported to this view. */
  get activeDeviceId(): string {
    return this.snapshot.active ?? "";
  }

  private paint(): void {
    this.root.innerHTML = this.html();
    this.attachEvents();
  }

  private html(): string {
    const options = this.snapshot.sources
      .map(
        (s) =>
          `<option value="${s.id}"${s.id === this.snapshot.active ? " selected" : ""}>${s.label || s.id}</option>`
      )
      .join("");
    return `<select data-audio-source>${options}</select>`;
  }

  private attachEvents(): void {
    const select = this.root.querySelector(
      "select[data-audio-source]"
    ) as HTMLSelectElement | null;
    select?.addEventListener("change", async () => {
      this.snapshot = await this.client.setActive(select.value);
      this.paint();
    });
  }
}
