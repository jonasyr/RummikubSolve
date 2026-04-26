import type { TileColor } from "../../types/api";

const VALID_KINDS = ["css", "sprite-atlas"] as const;
const VALID_COLORS = new Set<string>(["blue", "red", "black", "yellow"]);

function assertString(val: unknown, field: string): string {
  if (typeof val !== "string" || !val.trim()) {
    throw new Error(`manifest.${field} must be a non-empty string`);
  }
  return val;
}

function assertPositiveNumber(val: unknown, field: string): number {
  if (typeof val !== "number" || val <= 0) {
    throw new Error(`manifest.${field} must be a positive number`);
  }
  return val;
}

function assertNonNegativeInteger(val: unknown, field: string): number {
  if (typeof val !== "number" || !Number.isInteger(val) || val < 0) {
    throw new Error(`manifest.${field} must be a non-negative integer`);
  }
  return val;
}

export function validateManifest(raw: unknown): import("./types").SkinManifest {
  if (!raw || typeof raw !== "object") {
    throw new Error("manifest must be a non-null object");
  }
  const m = raw as Record<string, unknown>;

  assertString(m.id, "id");
  assertString(m.version, "version");

  if (!VALID_KINDS.includes(m.kind as never)) {
    throw new Error(`manifest.kind must be "css" or "sprite-atlas", got: ${String(m.kind)}`);
  }

  const dn = m.displayName as Record<string, unknown> | undefined;
  if (!dn || typeof dn.en !== "string" || !dn.en || typeof dn.de !== "string" || !dn.de) {
    throw new Error("manifest.displayName must have non-empty en and de strings");
  }

  if (m.kind === "sprite-atlas") {
    const sprite = m.sprite as Record<string, unknown> | undefined;
    if (!sprite || typeof sprite !== "object") {
      throw new Error("sprite-atlas manifest must include a sprite spec");
    }
    assertString(sprite.url, "sprite.url");
    assertPositiveNumber(sprite.tileWidth, "sprite.tileWidth");
    assertPositiveNumber(sprite.tileHeight, "sprite.tileHeight");

    const grid = sprite.grid as Record<string, unknown> | undefined;
    if (!grid || typeof grid !== "object") {
      throw new Error("manifest.sprite.grid is required");
    }
    assertPositiveNumber(grid.cols, "sprite.grid.cols");
    assertPositiveNumber(grid.rows, "sprite.grid.rows");
    assertNonNegativeInteger(grid.jokerRow, "sprite.grid.jokerRow");
    assertNonNegativeInteger(grid.jokerCol, "sprite.grid.jokerCol");

    if (!Array.isArray(grid.colorRowOrder)) {
      throw new Error("manifest.sprite.grid.colorRowOrder must be an array");
    }
    for (const c of grid.colorRowOrder as unknown[]) {
      if (!VALID_COLORS.has(c as string)) {
        throw new Error(`manifest.sprite.grid.colorRowOrder contains invalid color: ${String(c)}`);
      }
    }
    const unique = new Set(grid.colorRowOrder as string[]);
    if (unique.size !== (grid.colorRowOrder as unknown[]).length) {
      throw new Error("manifest.sprite.grid.colorRowOrder must not contain duplicates");
    }
  } else {
    // kind === "css"
    const css = m.css as Record<string, unknown> | undefined;
    if (!css || typeof css !== "object") {
      throw new Error("css manifest must include a css spec");
    }
    const colors = css.colors as Record<string, unknown> | undefined;
    if (!colors || typeof colors !== "object") {
      throw new Error("manifest.css.colors is required");
    }
    for (const required of ["blue", "red", "black", "yellow"] as TileColor[]) {
      if (!(required in colors)) {
        throw new Error(`manifest.css.colors missing key: ${required}`);
      }
    }
  }

  return raw as import("./types").SkinManifest;
}
