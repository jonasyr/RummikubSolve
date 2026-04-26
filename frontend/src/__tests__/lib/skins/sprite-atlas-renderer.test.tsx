import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import type { SkinManifest, TileRenderContext, TileSize } from "../../../lib/skins/types";
import { createSpriteAtlasRenderer } from "../../../lib/skins/sprite-atlas-renderer";

vi.mock("../../../lib/skins/preloader", () => ({
  preloadImage: vi.fn().mockResolvedValue({}),
}));

// ---------------------------------------------------------------------------
// Fixture
// ---------------------------------------------------------------------------

const FIXTURE_MANIFEST: SkinManifest = {
  id: "test-sprite",
  version: "1.0.0",
  kind: "sprite-atlas",
  displayName: { en: "Test", de: "Test" },
  description: { en: "Test", de: "Test" },
  thumbnail: "",
  sprite: {
    // 1×1 transparent GIF — a valid data-URI that Image can "load"
    url: "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7",
    tileWidth: 120,
    tileHeight: 135,
    grid: {
      cols: 13,
      rows: 5,
      colorRowOrder: ["blue", "red", "black", "yellow"],
      jokerRow: 4,
      jokerCol: 0,
    },
  },
};

const SIZE_PIXELS: Record<TileSize, { w: number; h: number }> = {
  xs: { w: 20, h: 24 },
  sm: { w: 28, h: 32 },
  md: { w: 36, h: 40 },
};

// ---------------------------------------------------------------------------
// Build parametric test cases: 52 color tiles × 3 sizes + 1 joker × 3 sizes
// ---------------------------------------------------------------------------

type TileCase = {
  label: string;
  ctx: TileRenderContext;
  expectedRow: number;
  expectedCol: number;
};

const COLORS = ["blue", "red", "black", "yellow"] as const;
const SIZES: TileSize[] = ["xs", "sm", "md"];

const tileCases: TileCase[] = [];

for (const size of SIZES) {
  for (let colorIdx = 0; colorIdx < COLORS.length; colorIdx++) {
    const color = COLORS[colorIdx];
    for (let n = 1; n <= 13; n++) {
      tileCases.push({
        label: `${color} ${n} size=${size}`,
        ctx: { color, number: n, isJoker: false, size },
        expectedRow: colorIdx,
        expectedCol: n - 1,
      });
    }
  }
  tileCases.push({
    label: `joker size=${size}`,
    ctx: { color: null, number: null, isJoker: true, size },
    expectedRow: 4,
    expectedCol: 0,
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("sprite-atlas-renderer — background position (all tiles × all sizes)", () => {
  const renderer = createSpriteAtlasRenderer(FIXTURE_MANIFEST);

  it.each(tileCases)("$label", ({ ctx, expectedRow, expectedCol }) => {
    const { w, h } = SIZE_PIXELS[ctx.size];
    const node = renderer.renderTileBody(ctx) as React.ReactElement<{ style: React.CSSProperties }>;

    expect(node).not.toBeNull();
    const s = node.props.style;
    expect(s.backgroundPosition).toBe(`${-expectedCol * w}px ${-expectedRow * h}px`);
    expect(s.backgroundSize).toBe(`${13 * w}px ${5 * h}px`);
    expect(s.backgroundImage).toBe(`url(${FIXTURE_MANIFEST.sprite!.url})`);
    expect(s.width).toBe(w);
    expect(s.height).toBe(h);
  });
});

describe("sprite-atlas-renderer — edge cases", () => {
  const renderer = createSpriteAtlasRenderer(FIXTURE_MANIFEST);

  it("returns null for placeholder tile (no color, not joker)", () => {
    const ctx: TileRenderContext = { color: null, number: null, isJoker: false, size: "md" };
    expect(renderer.renderTileBody(ctx)).toBeNull();
  });

  it("containerStyle returns empty object", () => {
    const ctx: TileRenderContext = { color: "blue", number: 1, isJoker: false, size: "md" };
    expect(renderer.containerStyle(ctx)).toEqual({});
  });

  it("isReady() is false before preload", () => {
    expect(renderer.isReady()).toBe(false);
  });

  it("isReady() is true after preload resolves", async () => {
    const r = createSpriteAtlasRenderer(FIXTURE_MANIFEST);
    await r.preload();
    expect(r.isReady()).toBe(true);
  });

  it("throws when manifest has no sprite spec", () => {
    const badManifest: SkinManifest = {
      id: "bad",
      version: "1.0.0",
      kind: "css",
      displayName: { en: "Bad", de: "Bad" },
      description: { en: "", de: "" },
      thumbnail: "",
      css: {
        colors: {
          blue: { bg: "bg-blue-600", fg: "text-white" },
          red: { bg: "bg-red-600", fg: "text-white" },
          black: { bg: "bg-black", fg: "text-white" },
          yellow: { bg: "bg-yellow-300", fg: "text-black" },
        },
        joker: { bg: "bg-white", fg: "text-black", symbol: "★" },
        placeholder: { bg: "bg-gray-200", fg: "text-gray-800" },
      },
    };
    expect(() => createSpriteAtlasRenderer(badManifest)).toThrow(/sprite/i);
  });
});
