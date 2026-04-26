import type { TileRenderContext, SkinRenderer, SkinManifest, CssSkinSpec } from "./types";

export function createCssRenderer(
  manifest: SkinManifest,
  spec: CssSkinSpec,
): SkinRenderer {
  return {
    manifest,
    containerStyle(ctx: TileRenderContext) {
      if (ctx.isJoker) {
        return { className: `${spec.joker.bg} ${spec.joker.fg}` };
      }
      if (!ctx.color) {
        return { className: `${spec.placeholder.bg} ${spec.placeholder.fg}` };
      }
      const { bg, fg } = spec.colors[ctx.color];
      return { className: `${bg} ${fg}` };
    },
    renderTileBody(ctx: TileRenderContext) {
      if (ctx.isJoker) return spec.joker.symbol;
      return ctx.number ?? "?";
    },
    isReady() {
      return true;
    },
    async preload() {},
  };
}
