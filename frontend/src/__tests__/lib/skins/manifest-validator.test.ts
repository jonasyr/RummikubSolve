import { describe, it, expect } from "vitest";
import { validateManifest } from "../../../lib/skins/manifest-validator";
import type { SkinManifest } from "../../../lib/skins/types";

const validCss: SkinManifest = {
  id: "default",
  version: "1.0.0",
  kind: "css",
  displayName: { en: "Default", de: "Standard" },
  description: { en: "Built-in CSS skin", de: "Eingebaute CSS-Skin" },
  thumbnail: "",
  css: {
    colors: {
      blue:   { bg: "bg-tile-blue",   fg: "text-white" },
      red:    { bg: "bg-tile-red",    fg: "text-white" },
      black:  { bg: "bg-tile-black",  fg: "text-white" },
      yellow: { bg: "bg-tile-yellow", fg: "text-gray-900" },
    },
    joker:       { bg: "bg-gray-800", fg: "text-yellow-400", symbol: "★" },
    placeholder: { bg: "bg-gray-300", fg: "text-gray-600" },
  },
};

const validSprite: SkinManifest = {
  id: "test-sprite",
  version: "1.0.0",
  kind: "sprite-atlas",
  displayName: { en: "Test", de: "Test" },
  description: { en: "Test", de: "Test" },
  thumbnail: "",
  sprite: {
    url: "/skins/test/v1/atlas.png",
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

describe("manifest-validator — valid manifests", () => {
  it("accepts a valid CSS manifest", () => {
    expect(() => validateManifest(validCss)).not.toThrow();
  });

  it("accepts a valid sprite-atlas manifest", () => {
    expect(() => validateManifest(validSprite)).not.toThrow();
  });
});

describe("manifest-validator — invalid manifests", () => {
  it("throws when id is empty string", () => {
    expect(() => validateManifest({ ...validCss, id: "" })).toThrow(/id/i);
  });

  it("throws when kind is unknown", () => {
    expect(() => validateManifest({ ...validCss, kind: "unknown" })).toThrow(/kind/i);
  });

  it("throws when sprite-atlas manifest has no sprite field", () => {
    const { sprite: _, ...noSprite } = validSprite;
    expect(() => validateManifest({ ...noSprite })).toThrow(/sprite/i);
  });

  it("throws when css manifest has no css field", () => {
    const { css: _, ...noCss } = validCss;
    expect(() => validateManifest({ ...noCss })).toThrow(/css/i);
  });

  it("throws when colorRowOrder contains duplicate colors", () => {
    expect(() =>
      validateManifest({
        ...validSprite,
        sprite: {
          ...validSprite.sprite!,
          grid: { ...validSprite.sprite!.grid, colorRowOrder: ["blue", "blue", "black", "yellow"] },
        },
      }),
    ).toThrow(/duplicate/i);
  });

  it("throws when tileWidth is 0", () => {
    expect(() =>
      validateManifest({
        ...validSprite,
        sprite: { ...validSprite.sprite!, tileWidth: 0 },
      }),
    ).toThrow(/tileWidth/i);
  });

  it("throws when displayName is missing", () => {
    const { displayName: _, ...noDisplayName } = validCss;
    expect(() => validateManifest({ ...noDisplayName })).toThrow(/displayName/i);
  });

  it("throws for non-object input", () => {
    expect(() => validateManifest(null)).toThrow();
    expect(() => validateManifest("string")).toThrow();
    expect(() => validateManifest(42)).toThrow();
  });
});
