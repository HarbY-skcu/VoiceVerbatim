type DeviceEnumerator = () => Promise<MediaDeviceInfo[]>;

export class AudioSourceSelector {
  private _activeDeviceId: string = "";

  constructor(
    private readonly root: HTMLElement,
    private readonly enumerateDevices: DeviceEnumerator = () =>
      navigator.mediaDevices.enumerateDevices()
  ) {}

  async render(): Promise<void> {
    const all = await this.enumerateDevices();
    const inputs = all.filter((d) => d.kind === "audioinput");

    const defaultDevice = inputs.find((d) => d.deviceId === "default") ?? inputs[0];
    this._activeDeviceId = defaultDevice?.deviceId ?? "";

    this.root.innerHTML = this.html(inputs);
    this.attachEvents();
  }

  get activeDeviceId(): string {
    return this._activeDeviceId;
  }

  private html(devices: MediaDeviceInfo[]): string {
    const options = devices
      .map(
        (d) =>
          `<option value="${d.deviceId}"${d.deviceId === this._activeDeviceId ? " selected" : ""}>${d.label || d.deviceId}</option>`
      )
      .join("");
    return `<select data-audio-source>${options}</select>`;
  }

  private attachEvents(): void {
    const select = this.root.querySelector(
      "select[data-audio-source]"
    ) as HTMLSelectElement | null;
    select?.addEventListener("change", () => {
      this._activeDeviceId = select.value;
    });
  }
}
