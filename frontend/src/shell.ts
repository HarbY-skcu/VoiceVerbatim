const TABS = ["All Notes", "Bookmarks"] as const;
type Tab = (typeof TABS)[number];

/**
 * Anything the Shell needs to trigger when the user navigates away from the
 * current Note view. Kept minimal (just the one method) so the Shell isn't
 * coupled to the full RecordingClient surface.
 */
export interface NavigationStopNotifier {
  navigationStop(): Promise<unknown>;
}

export class Shell {
  private activeTab: Tab = "All Notes";

  constructor(
    private readonly root: HTMLElement,
    private readonly navigationNotifier?: NavigationStopNotifier
  ) {}

  render(): void {
    this.root.innerHTML = this.html();
    this.attachEvents();
  }

  private html(): string {
    return `
      <div class="app-frame">
        <aside class="sidebar">
          <nav class="sidebar-tabs">
            ${TABS.map((tab) => this.tabButton(tab)).join("")}
          </nav>
          <div class="note-list" data-region="note-list"></div>
        </aside>
        <main class="main-pane" data-region="main-pane"></main>
        <footer class="recording-toolbar" data-region="recording-toolbar"></footer>
      </div>
    `;
  }

  private tabButton(tab: Tab): string {
    const isActive = tab === this.activeTab ? " active" : "";
    return `<button class="tab-btn${isActive}" data-tab="${tab}">${tab}</button>`;
  }

  private attachEvents(): void {
    this.root.querySelectorAll("[data-tab]").forEach((el) => {
      el.addEventListener("click", () => {
        const nextTab = el.getAttribute("data-tab") as Tab;
        if (nextTab === this.activeTab) {
          return;
        }
        this.activeTab = nextTab;
        // Switching sidebar tabs navigates away from the current Note view.
        this.navigationNotifier?.navigationStop();
        this.render();
      });
    });
  }
}
