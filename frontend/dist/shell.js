const TABS = ["All Notes", "Bookmarks"];
export class Shell {
    constructor(root) {
        this.root = root;
        this.activeTab = "All Notes";
    }
    render() {
        this.root.innerHTML = this.html();
        this.attachEvents();
    }
    html() {
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
    tabButton(tab) {
        const isActive = tab === this.activeTab ? " active" : "";
        return `<button class="tab-btn${isActive}" data-tab="${tab}">${tab}</button>`;
    }
    attachEvents() {
        this.root.querySelectorAll("[data-tab]").forEach((el) => {
            el.addEventListener("click", () => {
                this.activeTab = el.getAttribute("data-tab");
                this.render();
            });
        });
    }
}
