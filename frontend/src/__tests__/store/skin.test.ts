import { describe, it, expect, beforeEach, vi } from "vitest";

const PERSIST_KEY = "rummikub_active_skin_v1";

// Each test gets a fresh module (and therefore a fresh store + _callCounter = 0).
beforeEach(() => {
  localStorage.clear();
  vi.resetModules();
});

describe("skin store — happy path", () => {
  it("setSkin('high-contrast') updates state and persists", async () => {
    const { useSkinStore } = await import("../../store/skin");
    await useSkinStore.getState().setSkin("high-contrast");
    const state = useSkinStore.getState();
    expect(state.activeSkinId).toBe("high-contrast");
    expect(state.loadState).toBe("ready");
    expect(state.errorMessage).toBeNull();
    expect(localStorage.getItem(PERSIST_KEY)).toBe("high-contrast");
  });
});

describe("skin store — corrupted localStorage", () => {
  it("hydrates to default when stored value is garbage", async () => {
    localStorage.setItem(PERSIST_KEY, "}{garbage!@#");
    const { useSkinStore } = await import("../../store/skin");
    const state = useSkinStore.getState();
    expect(state.activeSkinId).toBe("default");
    expect(state.loadState).toBe("ready");
  });
});

describe("skin store — unknown skin id", () => {
  it("hydrates to default when stored id is not in registry", async () => {
    localStorage.setItem(PERSIST_KEY, "nonexistent-skin-xyz");
    const { useSkinStore } = await import("../../store/skin");
    const state = useSkinStore.getState();
    expect(state.activeSkinId).toBe("default");
    expect(state.loadState).toBe("ready");
  });
});

describe("skin store — race condition", () => {
  it("last setSkin call wins when called concurrently", async () => {
    const { useSkinStore } = await import("../../store/skin");
    // Fire both without awaiting — they race through the async preload microtasks.
    const p1 = useSkinStore.getState().setSkin("high-contrast");
    const p2 = useSkinStore.getState().setSkin("default");
    await Promise.all([p1, p2]);
    // "default" was requested last, so it must win.
    const state = useSkinStore.getState();
    expect(state.activeSkinId).toBe("default");
    expect(state.loadState).toBe("ready");
  });
});
