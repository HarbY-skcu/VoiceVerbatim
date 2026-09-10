# Code Review — Ticket 02: Audio Source Selection

**Beans ID:** `task-473ae85a`
**Files:** `frontend/src/audio-source-selector.ts`, `frontend/tests/audio-source-selector.test.ts`
**Tests:** 5/5 passing

---

## What was built

A single TypeScript class, `AudioSourceSelector`, that enumerates OS microphone input devices via an injected async function, renders a `<select>` dropdown into a given DOM element, pre-selects the system default, and tracks which device the user picks — all without starting a recording.

---

## Seam selection

Two public seams were agreed before writing tests:

1. **`render(): Promise<void>`** — observable via DOM queries after `await selector.render()`
2. **`activeDeviceId: string`** — a getter that reflects current selection state

Tests never reach into private methods (`html()`, `attachEvents()`) or access `_activeDeviceId` directly. Behavior through the public interface is the only thing under test.

**Why not test `navigator.mediaDevices` directly?** That is a browser platform API. Testing it would assert on the browser's behavior, not ours. The seam sits one level up: we test that `AudioSourceSelector` correctly filters, orders, and renders whatever a device enumerator returns.

---

## Dependency injection for the device enumerator

The most consequential design choice:

```typescript
type DeviceEnumerator = () => Promise<MediaDeviceInfo[]>;

constructor(
  private readonly root: HTMLElement,
  private readonly enumerateDevices: DeviceEnumerator = () =>
    navigator.mediaDevices.enumerateDevices()
) {}
```

`navigator.mediaDevices.enumerateDevices()` is unavailable in jsdom and requires a real browser with a granted microphone permission. Hardcoding it makes the class untestable without patching globals.

The injection makes the source of device data a constructor parameter with a sensible production default. Tests pass a synchronous-looking async stub; the running Electron app uses the real OS query. No mocking library, no `vi.spyOn`, no global mutation.

The type is narrowed to `DeviceEnumerator` — the minimal interface (`() => Promise<MediaDeviceInfo[]>`) rather than a full `MediaDevices` stub. This keeps the fake trivial to write.

---

## Default-device selection logic

```typescript
const defaultDevice =
  inputs.find((d) => d.deviceId === "default") ?? inputs[0];
this._activeDeviceId = defaultDevice?.deviceId ?? "";
```

Priority chain:
1. A device with `deviceId === "default"` — Chrome's synthetic entry for the OS-level default input.
2. `inputs[0]` — fallback for Firefox and some Electron builds that don't emit the synthetic entry.
3. `""` — only if no input devices are present.

Both branches are covered by separate tests.

---

## Full-redraw render pattern

`render()` replaces `root.innerHTML` entirely and re-attaches event listeners — the same pattern as `Shell` in ticket 01. The full redraw is appropriate here because `render()` is called once on app start. Surgical DOM diffing would add complexity with no current benefit; the ticket has no requirement for live device list refresh.

The `async` signature diverges from `Shell.render()` because `enumerateDevices()` is async (an OS call). Callers must `await selector.render()`, which the tests exercise explicitly to confirm correct assertion timing.

---

## Stable selector: `data-audio-source`

```typescript
// rendering:
return `<select data-audio-source>${options}</select>`;

// querying (in attachEvents and in tests):
root.querySelector("select[data-audio-source]")
```

`data-*` attributes as stable behavioral hooks, separate from CSS class names used for styling. A designer can rename or remove all CSS classes on the dropdown without breaking behavior or tests. Follows the `data-tab` pattern established in ticket 01.

---

## Test structure

**Fixture:** A single `FAKE_DEVICES` constant provides all devices: three `audioinput` and one `videoinput`. The `videoinput` is the negative case proving the filter works.

**Isolation:** Each test mounts a real `div` into `document.body` in `beforeEach` and removes it in `afterEach`. No state leaks between tests.

**Change-event dispatch:** The selection test sets `select.value` programmatically and dispatches a real `Event("change")`, testing the full path: user gesture → DOM event → listener → state update → public getter. No internals accessed.

---

## Acceptance criteria coverage

| Criterion | Test |
|---|---|
| Dropdown enumerates all OS microphone input devices | "dropdown lists only audioinput devices" |
| System default device pre-selected | "pre-selects the system default device" |
| Non-input devices excluded | same test — asserts `video-out` is absent |
| Selecting a device changes the active Audio Source | "activeDeviceId updates when user selects a different device" |
| Selection persists while app is open | "activeDeviceId returns the pre-selected device after render" |

The no-default-device fallback is an additional robustness test not in the ticket criteria — it covers Firefox and some Linux audio stacks.

---

## What is deliberately deferred

| Deferred concern | Reason |
|---|---|
| `devicechange` event | Runtime device plug/unplug not in ticket criteria |
| `getUserMedia` / permission prompt | Belongs to ticket 03 (Record / Stop / Pause) |
| Persistence across restarts | Ticket explicitly excludes this |
| Mounting into the Shell toolbar | A one-liner in `renderer.ts`, left for ticket 03 when the toolbar gets its first real content |
| Empty-state UI (no devices) | UX decision not specified in the ticket |

The wiring into `renderer.ts` when ready:
```typescript
const toolbar = document.querySelector('[data-region="recording-toolbar"]')!;
await new AudioSourceSelector(toolbar as HTMLElement).render();
```
