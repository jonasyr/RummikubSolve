import type { SkinRenderer } from "./types";
import { defaultSkinRenderer } from "./default-skin";

const registry = new Map<string, SkinRenderer>([
  ["default", defaultSkinRenderer],
]);

export function getSkinRenderer(id: string): SkinRenderer {
  return registry.get(id) ?? defaultSkinRenderer;
}

export function getRegistry(): ReadonlyMap<string, SkinRenderer> {
  return registry;
}
