import type React from "react";
import type { TileColor } from "@/types/api";

export type SkinId = string;
export type SkinKind = "css" | "sprite-atlas";
export type TileSize = "xs" | "sm" | "md";

export interface TileRenderContext {
  color: TileColor | null;
  number: number | null;
  isJoker: boolean;
  size: TileSize;
}

export interface LocalizedText {
  en: string;
  de: string;
}

export interface SpriteAtlasSpec {
  url: string;
  tileWidth: number;
  tileHeight: number;
  grid: {
    cols: number;
    rows: number;
    colorRowOrder: TileColor[];
    jokerRow: number;
    jokerCol: number;
  };
}

export interface CssSkinSpec {
  colors: Record<TileColor, { bg: string; fg: string }>;
  joker: { bg: string; fg: string; symbol: string };
  placeholder: { bg: string; fg: string };
}

export interface SkinManifest {
  id: SkinId;
  version: string;
  kind: SkinKind;
  displayName: LocalizedText;
  description: LocalizedText;
  author?: string;
  thumbnail: string;
  sprite?: SpriteAtlasSpec;
  css?: CssSkinSpec;
}

export interface SkinRenderer {
  manifest: SkinManifest;
  renderTileBody(ctx: TileRenderContext): React.ReactNode;
  containerStyle(ctx: TileRenderContext): {
    className?: string;
    style?: React.CSSProperties;
  };
  isReady(): boolean;
  preload(): Promise<void>;
}
