const TABS = ["All Notes", "Bookmarks"] as const;
type Tab = (typeof TABS)[number];

export class Shell {
  private activeTab: Tab = "All Notes";

  constructor(private readonly root: HTMLElement) {}

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
        this.activeTab = el.getAttribute("data-tab") as Tab;
        this.render();
      });
    });
  }
}
