import React from "react";
import type { TileRenderContext, TileSize, SkinRenderer, SkinManifest } from "./types";
import { preloadImage } from "./preloader";

const SIZE_PIXELS: Record<TileSize, { w: number; h: number }> = {
  xs: { w: 20, h: 24 }, // w-5  h-6
  sm: { w: 28, h: 32 }, // w-7  h-8
  md: { w: 36, h: 40 }, // w-9  h-10
};

export function createSpriteAtlasRenderer(manifest: SkinManifest): SkinRenderer {
  if (!manifest.sprite) {
    throw new Error(`createSpriteAtlasRenderer: manifest "${manifest.id}" is missing sprite spec`);
  }
  const spec = manifest.sprite;
  let ready = false;

  return {
    manifest,

    containerStyle(_ctx: TileRenderContext) {
      // Sprite body div provides all visuals; outer Tile div keeps its Tailwind size classes.
      return {};
    },

    renderTileBody(ctx: TileRenderContext): React.ReactNode {
      const { w: renderW, h: renderH } = SIZE_PIXELS[ctx.size];
      let col: number;
      let row: number;

      if (ctx.isJoker) {
        row = spec.grid.jokerRow;
        col = spec.grid.jokerCol;
      } else if (ctx.color !== null) {
        row = spec.grid.colorRowOrder.indexOf(ctx.color);
        col = (ctx.number ?? 1) - 1;
      } else {
        return null; // placeholder tile — no sprite cell defined
      }

      return React.createElement("div", {
        style: {
          width: renderW,
          height: renderH,
          backgroundImage: `url(${spec.url})`,
          // Integer arithmetic: no fractional-pixel drift (spec R-pixel-drift mitigation).
          backgroundSize: `${spec.grid.cols * renderW}px ${spec.grid.rows * renderH}px`,
          backgroundPosition: `${-col * renderW}px ${-row * renderH}px`,
          backgroundRepeat: "no-repeat",
        },
      });
    },

    isReady() {
      return ready;
    },

    async preload() {
      await preloadImage(spec.url);
      ready = true;
    },
  };
}
