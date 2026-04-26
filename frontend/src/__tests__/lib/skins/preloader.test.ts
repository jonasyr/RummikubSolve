import { describe, it, expect, beforeEach, vi } from "vitest";

// Fresh module (and therefore fresh _cache) for every test.
beforeEach(() => {
  vi.resetModules();
});

// ---------------------------------------------------------------------------
// Minimal Image mock factory — only properties the preloader touches.
// ---------------------------------------------------------------------------
type ImageMockOpts = { fireLoad?: boolean; fireError?: boolean; delay?: number };

function mockImage({ fireLoad, fireError, delay = 0 }: ImageMockOpts = {}) {
  return class MockImage {
    src = "";
    crossOrigin = "";
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;
    constructor() {
      if (fireLoad) {
        setTimeout(() => this.onload?.(), delay);
      } else if (fireError) {
        setTimeout(() => this.onerror?.(), delay);
      }
      // If neither, the Promise never resolves (used for timeout/idempotency tests).
    }
  };
}

describe("preloader — resolves on load", () => {
  it("resolves with an Image when onload fires", async () => {
    globalThis.Image = mockImage({ fireLoad: true }) as unknown as typeof Image;
    const { preloadImage } = await import("../../../lib/skins/preloader");
    const img = await preloadImage("/ok.png");
    expect(img).toBeDefined();
  });
});

describe("preloader — rejects on error", () => {
  it("rejects when onerror fires and removes entry from cache", async () => {
    globalThis.Image = mockImage({ fireError: true }) as unknown as typeof Image;
    const { preloadImage } = await import("../../../lib/skins/preloader");
    const p1 = preloadImage("/fail.png");
    await expect(p1).rejects.toThrow(/preloadImage failed/i);

    // After rejection the cache entry must be gone — second call is a new Promise.
    const p2 = preloadImage("/fail.png");
    expect(p1).not.toBe(p2);
    // Suppress the second rejection so it doesn't become an unhandled promise.
    p2.catch(() => {});
  });
});

describe("preloader — timeout", () => {
  it("rejects with timeout message when image never loads", async () => {
    vi.useFakeTimers();
    globalThis.Image = mockImage() as unknown as typeof Image; // never fires
    const { preloadImage } = await import("../../../lib/skins/preloader");

    const promise = preloadImage("/slow.png", 100);
    vi.advanceTimersByTime(200);
    await expect(promise).rejects.toThrow(/timeout/i);

    vi.useRealTimers();
  });
});

describe("preloader — idempotency", () => {
  it("returns the same Promise for the same URL (concurrent calls)", async () => {
    globalThis.Image = mockImage() as unknown as typeof Image; // never resolves; just need the reference
    const { preloadImage } = await import("../../../lib/skins/preloader");

    const p1 = preloadImage("/same.png");
    const p2 = preloadImage("/same.png");
    expect(p1).toBe(p2);
  });

  it("returns distinct Promises for different URLs", async () => {
    globalThis.Image = mockImage() as unknown as typeof Image;
    const { preloadImage } = await import("../../../lib/skins/preloader");

    const p1 = preloadImage("/a.png");
    const p2 = preloadImage("/b.png");
    expect(p1).not.toBe(p2);
  });
});
