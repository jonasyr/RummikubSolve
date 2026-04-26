import type { SkinRenderer } from "./types";
import { defaultSkinRenderer } from "./default-skin";
import { highContrastSkinRenderer } from "./high-contrast-skin";

const registry = new Map<string, SkinRenderer>([
  ["default", defaultSkinRenderer],
  ["high-contrast", highContrastSkinRenderer],
]);

export function getSkinRenderer(id: string): SkinRenderer {
  return registry.get(id) ?? defaultSkinRenderer;
}

export function getRegistry(): ReadonlyMap<string, SkinRenderer> {
  return registry;
}
