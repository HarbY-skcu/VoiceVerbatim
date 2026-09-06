# Code Review — Ticket 01: Shell & Navigation Frame

**Beans ID:** `task-aab684bb`  
**Status:** ready-for-agent  
**Blocked by:** None  
**Branch:** `create-user-stories` (worktree of `PythonProject/master`)

---

## What This Ticket Builds

Ticket 01 is the skeleton of the entire Voice-to-Text Notes app. It establishes the visual frame — the sidebar with two tabs ("All Notes" and "Bookmarks"), an empty note list area, a main pane, and a non-functional recording toolbar strip at the bottom. No recording, no notes, no persistence. Every subsequent ticket builds *inside* this frame.

---

## Project Architecture Overview

The project is split into two independently runnable layers that are intentionally decoupled at this stage:

```
user-story-work/
├── frontend/          ← Electron + TypeScript UI
│   ├── electron/      ← Native process (main + preload)
│   ├── src/           ← Renderer process (TypeScript → compiled JS)
│   ├── dist/          ← Compiled output (tsc writes here)
│   └── tests/         ← Vitest unit tests (jsdom)
└── backend/           ← FastAPI Python API
    ├── app/main.py
    └── tests/
```

At ticket 01, the frontend renders entirely from static local data — it does **not** talk to the backend yet. The backend's `/api/sidebar/tabs` endpoint exists to model the data contract for when the two layers eventually connect. This is a deliberate staging decision: prove the UI shape works before wiring up real data.

---

## Architectural Decisions

### 1. Electron for the Desktop Shell

The app is a native desktop app built on **Electron**, which bundles Chromium (the rendering engine) and Node.js into a distributable `.exe`/`.app`. The choice gives access to OS APIs (microphone, file system) that a plain web app cannot reach, while still letting the UI be written in HTML/CSS/TypeScript.

**Why not a pure web app?** Microphone capture in a web context requires browser permissions and is limited at the OS level. A native desktop wrapper removes those constraints and allows direct file system access for note persistence in later tickets.

**Two-process model:**

| Process | File | Role |
|---|---|---|
| Main process | `electron/main.js` | Owns the OS window; runs Node.js |
| Renderer process | `src/renderer.ts` (→ `dist/renderer.js`) | Runs in the sandboxed Chromium page |
| Bridge | `electron/preload.js` | Safe channel between the two |

---

### 2. Context Isolation + Preload Bridge

```js
// electron/main.js
const win = new BrowserWindow({
  webPreferences: {
    preload: path.join(__dirname, "preload.js"),
    contextIsolation: true,   // ← key security flag
  },
});
```

`contextIsolation: true` means the renderer page's JavaScript cannot access Node.js APIs directly. Only what the preload script explicitly exposes is available to renderer code. This is Electron's security best practice — without it, malicious web content loaded in the window could access the file system or spawn shell processes.

```js
// electron/preload.js
contextBridge.exposeInMainWorld("api", {
  // Expanded in future tickets as IPC channels are needed
});
```

The preload intentionally exposes nothing yet. The comment is a deliberate placeholder: as future tickets add recording or file persistence, named IPC channels will be added here under `window.api`. This keeps the surface area minimal and auditable.

---

### 3. Shell Class — Render-on-State-Change Pattern

```ts
// frontend/src/shell.ts
const TABS = ["All Notes", "Bookmarks"] as const;
type Tab = (typeof TABS)[number];

export class Shell {
  private activeTab: Tab = "All Notes";

  constructor(private readonly root: HTMLElement) {}

  render(): void {
    this.root.innerHTML = this.html();
    this.attachEvents();
  }
```

**`as const` + union type:** `TABS` is a readonly tuple. `typeof TABS[number]` derives the union type `"All Notes" | "Bookmarks"` automatically from the array. This means adding or removing a tab name from the `TABS` array is the *only* change needed — the type and all rendered buttons update automatically. It is a zero-drift pattern.

**`render()` is a full redraw:** Rather than surgically updating the DOM, `render()` replaces `root.innerHTML` entirely and re-attaches event listeners. This is simple and correct for this stage. It is the same approach React popularised, though done manually here without a virtual DOM. The cost is negligible for a sidebar with two buttons.

**State lives on the instance:** `activeTab` is private class state. Tab clicks update it and call `render()` again — effectively a tiny state machine with one variable.

```ts
  private attachEvents(): void {
    this.root.querySelectorAll("[data-tab]").forEach((el) => {
      el.addEventListener("click", () => {
        this.activeTab = el.getAttribute("data-tab") as Tab;
        this.render();
      });
    });
  }
```

Event listeners are re-attached after every render because the DOM nodes are replaced. The `data-tab` attribute serves as a stable selector independent of CSS class names — selectors driven by `data-*` attributes are a common pattern for separating behaviour from styling concerns.

---

### 4. Layout — CSS Grid Named Areas

```css
/* frontend/src/styles.css */
.app-frame {
  display: grid;
  grid-template-columns: 220px 1fr;
  grid-template-rows: 1fr 56px;
  grid-template-areas:
    "sidebar main"
    "toolbar toolbar";
  height: 100vh;
}
```

The entire app layout is expressed in one CSS Grid declaration. Named template areas (`sidebar`, `main`, `toolbar`) make the intent readable directly from the CSS. `1fr` is a fractional unit meaning "take the remaining space". The toolbar spans the full bottom row (`toolbar toolbar`) regardless of column count.

This decision makes future layout changes surgical — moving the toolbar to the side, for example, requires changing only this grid definition and the `grid-area` property on `.recording-toolbar`, not touching the component itself.

**Design tokens via CSS custom properties:**

```css
:root {
  --bg: #1e1e2e;
  --surface: #252535;
  --border: #353550;
  --text: #cdd6f4;
  --text-muted: #6c7086;
  --accent: #89b4fa;
  --active-tab-bg: #313244;
}
```

All colours are defined once on `:root` as CSS variables. Every component references `var(--accent)` etc. rather than hardcoded hex values. Changing the theme later means changing seven lines at the top of one file, not hunting through the stylesheet.

The colour palette follows the [Catppuccin Mocha](https://github.com/catppuccin/catppuccin) scheme — a community dark-mode palette designed for legibility and contrast.

---

### 5. Entry Point — `renderer.ts`

```ts
// frontend/src/renderer.ts
import { Shell } from "./shell.js";

const root = document.getElementById("app")!;
const shell = new Shell(root);
shell.render();
```

Three lines. The `!` after `getElementById` is a TypeScript non-null assertion — it tells the compiler "I know this element exists." It is safe here because `index.html` always provides `<div id="app">`. The entry point's only job is to locate the mount point and hand it to the Shell.

---

### 6. HTML Structure

```html
<!-- frontend/src/index.html -->
<body>
  <div id="app"></div>
  <script type="module" src="../dist/renderer.js"></script>
</body>
```

`type="module"` enables ES Module semantics in the browser — the script can use `import`/`export` natively. It also defers execution automatically (no `defer` attribute needed). The `src` points to the compiled output in `dist/`, not the TypeScript source.

---

### 7. Backend — FastAPI Data Contract

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Voice-to-Text Notes")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    ...
)

SIDEBAR_TABS = ["All Notes", "Bookmarks"]

@app.get("/api/sidebar/tabs")
def get_sidebar_tabs():
    return {"tabs": SIDEBAR_TABS, "active": SIDEBAR_TABS[0]}
```

**FastAPI** is a Python web framework that auto-generates an OpenAPI schema from type hints. The endpoint `/api/sidebar/tabs` returns `{ tabs: [...], active: "..." }` — the same data shape the frontend currently hardcodes. This defines the contract for when the two layers connect.

**CORS wildcard (`allow_origins=["*"]`):** This is intentionally permissive for local development. In production, this should be tightened to the Electron app's origin or removed entirely in favour of direct IPC communication (Electron main process as the API consumer, no HTTP needed).

The backend is not called by the frontend in ticket 01. It exists to establish the data shape early, so the shape can be reviewed and corrected before implementation continues.

---

### 8. Testing Strategy

**Frontend — Vitest + jsdom:**

```ts
// frontend/tests/shell.test.ts
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { Shell } from "../src/shell";
```

Vitest runs in Node.js but simulates a browser DOM via **jsdom** (`environment: "jsdom"` in `vitest.config.ts`). This means `document`, `querySelector`, and `.click()` all work without opening a real browser. The tests exercise the Shell class by creating a real DOM element, calling `render()`, and asserting on the resulting HTML structure.

Each test:
1. Creates a fresh `div` and mounts it to `document.body` (in `beforeEach`)
2. Instantiates `Shell`, calls `render()`
3. Queries the DOM for expected elements
4. Cleans up by removing the container (in `afterEach`)

Six tests cover: tab presence, default active state, tab switching in both directions, and presence of the main pane and toolbar regions.

**Backend — FastAPI TestClient:**

```python
# backend/tests/test_sidebar.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_sidebar_tabs_returns_all_notes_and_bookmarks():
    response = client.get("/api/sidebar/tabs")
    assert response.status_code == 200
    data = response.json()
    assert data["tabs"] == ["All Notes", "Bookmarks"]
```

FastAPI's `TestClient` wraps the ASGI app with `httpx`, letting you send real HTTP requests without starting a server. Tests assert on both the response status and the JSON body shape.

---

## File Map

| File | Purpose |
|---|---|
| `frontend/electron/main.js` | Creates the OS window; bootstraps Electron |
| `frontend/electron/preload.js` | IPC bridge (empty at ticket 01) |
| `frontend/src/index.html` | HTML entry point; mounts `#app` |
| `frontend/src/renderer.ts` | Entry script; instantiates Shell |
| `frontend/src/shell.ts` | All UI state and rendering logic |
| `frontend/src/styles.css` | Layout (CSS Grid) and design tokens |
| `frontend/dist/renderer.js` | Compiled output of `renderer.ts` |
| `frontend/dist/shell.js` | Compiled output of `shell.ts` |
| `frontend/tests/shell.test.ts` | Vitest tests for Shell behaviour |
| `frontend/vitest.config.ts` | Test runner config (jsdom environment) |
| `frontend/package.json` | npm scripts and dev dependencies |
| `frontend/tsconfig.json` | TypeScript compiler options |
| `backend/app/main.py` | FastAPI app; `/api/sidebar/tabs` endpoint |
| `backend/tests/test_sidebar.py` | pytest tests for the sidebar endpoint |
| `backend/requirements.txt` | Python dependencies (FastAPI, uvicorn) |
| `.scratch/voice-to-text-mvp/issues/01-shell-and-navigation-frame.md` | Beans ticket with acceptance criteria |
| `CONTEXT.md` | Domain glossary (authoritative language for the app) |

---

## Acceptance Criteria vs. Implementation

| Criterion | Implemented by |
|---|---|
| App window opens on launch | `electron/main.js` → `BrowserWindow` |
| Sidebar shows "All Notes" and "Bookmarks" tabs | `Shell.html()` → `.sidebar-tabs` |
| Switching tabs changes the active view | `Shell.attachEvents()` + `render()` cycle |
| Main pane is empty but present | `<main data-region="main-pane">` |
| Recording toolbar area present but non-functional | `<footer data-region="recording-toolbar">` |

All five criteria are met by the current implementation.

---

## Further Reading

### Electron
- [Electron docs — Process Model](https://www.electronjs.org/docs/latest/tutorial/process-model) — explains the main/renderer/preload split
- [Electron docs — Context Isolation](https://www.electronjs.org/docs/latest/tutorial/context-isolation) — why `contextIsolation: true` matters
- [Electron docs — IPC](https://www.electronjs.org/docs/latest/tutorial/ipc) — how main and renderer communicate via `contextBridge` (relevant for future tickets)

### TypeScript
- [TypeScript Handbook — `as const`](https://www.typescriptlang.org/docs/handbook/2/everyday-types.html#literal-types) — how literal types and const assertions work
- [TypeScript Handbook — Indexed Access Types](https://www.typescriptlang.org/docs/handbook/2/indexed-access-types.html) — explains `typeof TABS[number]`

### CSS Grid
- [MDN — CSS Grid Layout](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_grid_layout) — comprehensive reference
- [MDN — grid-template-areas](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-template-areas) — named area syntax used in `.app-frame`
- [CSS Tricks — Complete Guide to Grid](https://css-tricks.com/snippets/css/complete-guide-grid/) — visual reference for all grid properties

### FastAPI
- [FastAPI docs — First Steps](https://fastapi.tiangolo.com/tutorial/first-steps/) — getting started with route definitions
- [FastAPI docs — CORS](https://fastapi.tiangolo.com/tutorial/cors/) — configuring allowed origins (relevant when tightening the wildcard)
- [FastAPI docs — Testing](https://fastapi.tiangolo.com/tutorial/testing/) — how `TestClient` works

### Vitest + jsdom
- [Vitest docs](https://vitest.dev/guide/) — test runner used for the frontend
- [jsdom GitHub](https://github.com/jsdom/jsdom) — the DOM simulator that lets browser tests run in Node.js
- [Vitest — Environment config](https://vitest.dev/config/#environment) — how to switch between `node`, `jsdom`, and `happy-dom`

### Beans (ticket tracking)
- The `/plan-beans` skill in `.claude/skills/plan-beans/SKILL.md` explains how Beans IDs are assigned, how dependencies are declared, and how the execution frontier (`beans ready`) is queried.
