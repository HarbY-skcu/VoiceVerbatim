import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { Shell } from "../src/shell";
describe("Shell & Navigation Frame", () => {
    let container;
    beforeEach(() => {
        container = document.createElement("div");
        document.body.appendChild(container);
    });
    afterEach(() => {
        container.remove();
    });
    it("renders All Notes and Bookmarks sidebar tabs", () => {
        const shell = new Shell(container);
        shell.render();
        const tabs = container.querySelectorAll("[data-tab]");
        const tabNames = Array.from(tabs).map((t) => t.textContent?.trim());
        expect(tabNames).toContain("All Notes");
        expect(tabNames).toContain("Bookmarks");
    });
    it("sets All Notes as the active tab by default", () => {
        const shell = new Shell(container);
        shell.render();
        const activeTab = container.querySelector("[data-tab].active");
        expect(activeTab?.textContent?.trim()).toBe("All Notes");
    });
    it("switches active tab when Bookmarks is clicked", () => {
        const shell = new Shell(container);
        shell.render();
        const bookmarksTab = container.querySelector('[data-tab="Bookmarks"]');
        bookmarksTab.click();
        const activeTab = container.querySelector("[data-tab].active");
        expect(activeTab?.textContent?.trim()).toBe("Bookmarks");
    });
    it("switches back to All Notes when clicked after Bookmarks", () => {
        const shell = new Shell(container);
        shell.render();
        container.querySelector('[data-tab="Bookmarks"]').click();
        container.querySelector('[data-tab="All Notes"]').click();
        const activeTab = container.querySelector("[data-tab].active");
        expect(activeTab?.textContent?.trim()).toBe("All Notes");
    });
    it("renders main pane area", () => {
        const shell = new Shell(container);
        shell.render();
        expect(container.querySelector("[data-region='main-pane']")).not.toBeNull();
    });
    it("renders recording toolbar area", () => {
        const shell = new Shell(container);
        shell.render();
        expect(container.querySelector("[data-region='recording-toolbar']")).not.toBeNull();
    });
});
