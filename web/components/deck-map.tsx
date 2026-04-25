"use client";
import dynamic from "next/dynamic";

// Single dynamic boundary that loads ALL deck.gl + luma.gl modules in one
// chunk. Mixing top-level dynamic-import with require() inside a hook causes
// webpack to bundle two copies of luma.gl, which then trips
// "luma.gl: This version of luma.gl has already been initialized".
export const DeckMap = dynamic(
  () => import("./deck-map-impl").then(m => m.default),
  {
    ssr: false,
    loading: () => (
      <div
        className="rounded-xl border border-border/60 bg-gradient-to-br from-slate-950 to-slate-900 flex items-center justify-center text-sm text-muted-foreground"
        style={{ height: 600 }}
      >
        Loading map…
      </div>
    ),
  }
);
