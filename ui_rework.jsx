import { useState } from “react”;

// ─── Tile rendering ────────────────────────────────────────────────────────
const TILE_BG = {
blue: “#1d4ed8”,
red: “#dc2626”,
black: “#1f2937”,
yellow: “#d97706”,
joker: “#374151”,
};

function Tile({ color, number, isJoker, size = “md”, highlight, ghost, provenance, label }) {
const s = size === “xs” ? 24 : size === “sm” ? 32 : 40;
const fs = size === “xs” ? 10 : size === “sm” ? 12 : 15;
const bg = isJoker ? TILE_BG.joker : TILE_BG[color] || “#999”;
const textColor = color === “yellow” ? “#1a1a1a” : “#fff”;

return (
<div style={{ position: “relative”, display: “inline-flex”, flexDirection: “column”, alignItems: “center”, gap: 2 }}>
<div
style={{
width: s,
height: s * 1.15,
borderRadius: 4,
background: ghost ? “transparent” : bg,
border: ghost ? `2px dashed ${bg}40` : highlight ? `2px solid #facc15` : `1px solid rgba(255,255,255,0.15)`,
color: ghost ? `${bg}60` : isJoker ? “#facc15” : textColor,
display: “flex”,
alignItems: “center”,
justifyContent: “center”,
fontWeight: 700,
fontSize: fs,
fontFamily: “‘JetBrains Mono’, monospace”,
opacity: ghost ? 0.4 : 1,
boxShadow: highlight ? “0 0 8px rgba(250,204,21,0.4)” : “0 1px 3px rgba(0,0,0,0.3)”,
transition: “all 0.2s”,
}}
>
{isJoker ? “★” : number}
</div>
{provenance && (
<span style={{ fontSize: 8, color: provenance === “hand” ? “#22c55e” : “#94a3b8”, fontWeight: 600, letterSpacing: 0.5 }}>
{provenance === “hand” ? “HAND” : `SET ${provenance}`}
</span>
)}
{label && (
<span style={{ fontSize: 8, color: “#64748b”, fontWeight: 600, position: “absolute”, top: -14, whiteSpace: “nowrap” }}>
{label}
</span>
)}
</div>
);
}

function TileGroup({ tiles, label, border, bg, badge, badgeColor, compact }) {
return (
<div
style={{
display: “flex”,
flexDirection: “column”,
gap: 4,
padding: compact ? “6px 8px” : “8px 12px”,
borderRadius: 8,
border: `1px solid ${border || "#334155"}`,
background: bg || “#1e293b”,
minWidth: 60,
}}
>
{(label || badge) && (
<div style={{ display: “flex”, alignItems: “center”, gap: 6, marginBottom: 2 }}>
{label && <span style={{ fontSize: 10, color: “#94a3b8”, fontWeight: 600, textTransform: “uppercase”, letterSpacing: 1 }}>{label}</span>}
{badge && (
<span
style={{
fontSize: 9,
fontWeight: 700,
padding: “1px 6px”,
borderRadius: 4,
background: badgeColor || “#334155”,
color: “#fff”,
letterSpacing: 0.5,
}}
>
{badge}
</span>
)}
</div>
)}
<div style={{ display: “flex”, gap: 3, flexWrap: “wrap” }}>
{tiles.map((t, i) => (
<Tile key={i} {…t} />
))}
</div>
</div>
);
}

// ─── Arrow SVG ─────────────────────────────────────────────────────────────
function Arrow({ direction = “right”, color = “#475569”, size = 20 }) {
if (direction === “right”) {
return (
<svg width={size} height={size} viewBox=“0 0 24 24” fill=“none” style={{ flexShrink: 0 }}>
<path d="M5 12h14M13 5l7 7-7 7" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
</svg>
);
}
return (
<svg width={size} height={size} viewBox=“0 0 24 24” fill=“none” style={{ flexShrink: 0 }}>
<path d="M12 5v14M5 12l7 7 7-7" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
</svg>
);
}

// ─── Section containers ────────────────────────────────────────────────────
function Card({ children, active, onClick, style }) {
return (
<div
onClick={onClick}
style={{
background: active ? “#1e293b” : “#0f172a”,
border: `1px solid ${active ? "#3b82f6" : "#1e293b"}`,
borderRadius: 12,
padding: 20,
cursor: onClick ? “pointer” : “default”,
transition: “all 0.2s”,
…style,
}}
>
{children}
</div>
);
}

function Badge({ children, color }) {
const colors = {
green: { bg: “#166534”, text: “#4ade80” },
blue: { bg: “#1e3a5f”, text: “#60a5fa” },
amber: { bg: “#78350f”, text: “#fbbf24” },
red: { bg: “#7f1d1d”, text: “#f87171” },
gray: { bg: “#374151”, text: “#9ca3af” },
purple: { bg: “#4c1d95”, text: “#a78bfa” },
};
const c = colors[color] || colors.gray;
return (
<span
style={{
fontSize: 10,
fontWeight: 700,
padding: “2px 8px”,
borderRadius: 4,
background: c.bg,
color: c.text,
letterSpacing: 0.5,
textTransform: “uppercase”,
display: “inline-block”,
}}
>
{children}
</span>
);
}

// ═══════════════════════════════════════════════════════════════════════════
// APPROACH MOCKUPS
// ═══════════════════════════════════════════════════════════════════════════

function Approach1_SnapshotDiff() {
return (
<div style={{ display: “flex”, flexDirection: “column”, gap: 16 }}>
{/* Summary */}
<div style={{ display: “flex”, gap: 8, flexWrap: “wrap” }}>
<Badge color="green">2 tiles placed</Badge>
<Badge color="blue">Optimal</Badge>
<Badge color="gray">42ms</Badge>
</div>

```
  {/* Two-column before/after */}
  <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: 12, alignItems: "start" }}>
    {/* BEFORE column */}
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <span style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", letterSpacing: 1, textTransform: "uppercase" }}>Before</span>
      <TileGroup
        tiles={[
          { color: "red", number: 3 },
          { color: "red", number: 4 },
          { color: "red", number: 5 },
        ]}
        label="Set 1"
        compact
      />
      <TileGroup
        tiles={[
          { color: "blue", number: 7 },
          { color: "red", number: 7 },
          { color: "black", number: 7 },
        ]}
        label="Set 2"
        compact
      />
      <TileGroup
        tiles={[
          { color: "blue", number: 10 },
          { color: "blue", number: 11 },
          { color: "blue", number: 12 },
        ]}
        label="Set 3"
        compact
      />
      <div style={{ marginTop: 8, padding: "8px 12px", borderRadius: 8, border: "1px dashed #475569", background: "#0f172a22" }}>
        <span style={{ fontSize: 10, color: "#94a3b8", fontWeight: 600, display: "block", marginBottom: 4 }}>HAND</span>
        <div style={{ display: "flex", gap: 3 }}>
          <Tile color="red" number={6} size="sm" highlight />
          <Tile color="yellow" number={7} size="sm" highlight />
        </div>
      </div>
    </div>

    {/* Arrow */}
    <div style={{ display: "flex", alignItems: "center", paddingTop: 30 }}>
      <Arrow size={28} color="#3b82f6" />
    </div>

    {/* AFTER column */}
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <span style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", letterSpacing: 1, textTransform: "uppercase" }}>After</span>
      <TileGroup
        tiles={[
          { color: "red", number: 3 },
          { color: "red", number: 4 },
          { color: "red", number: 5 },
          { color: "red", number: 6, size: "sm", highlight: true },
        ]}
        label="Set 1"
        badge="EXTENDED"
        badgeColor="#1e40af"
        border="#3b82f6"
        compact
      />
      <TileGroup
        tiles={[
          { color: "blue", number: 7 },
          { color: "red", number: 7 },
          { color: "black", number: 7 },
          { color: "yellow", number: 7, highlight: true },
        ]}
        label="Set 2"
        badge="EXTENDED"
        badgeColor="#1e40af"
        border="#3b82f6"
        compact
      />
      <TileGroup
        tiles={[
          { color: "blue", number: 10 },
          { color: "blue", number: 11 },
          { color: "blue", number: 12 },
        ]}
        label="Set 3"
        badge="UNCHANGED"
        border="#334155"
        compact
      />
      <div style={{ marginTop: 8, padding: "8px 12px", borderRadius: 8, border: "1px dashed #22c55e44", background: "#16a34a10" }}>
        <span style={{ fontSize: 10, color: "#4ade80", fontWeight: 600 }}>✓ Hand empty</span>
      </div>
    </div>
  </div>
</div>
```

);
}

function Approach2_InstructionChecklist() {
const [checked, setChecked] = useState([false, false]);
const toggle = (i) => setChecked((p) => p.map((v, j) => (j === i ? !v : v)));

return (
<div style={{ display: “flex”, flexDirection: “column”, gap: 12 }}>
<div style={{ display: “flex”, gap: 8, flexWrap: “wrap” }}>
<Badge color="green">2 tiles placed</Badge>
<Badge color="blue">Optimal</Badge>
</div>

```
  {/* Final board (collapsed, just for reference) */}
  <div style={{ padding: "8px 12px", borderRadius: 8, background: "#1e293b", border: "1px solid #334155" }}>
    <span style={{ fontSize: 10, color: "#64748b", fontWeight: 600, letterSpacing: 1 }}>RESULT BOARD</span>
    <div style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
      <TileGroup
        tiles={[
          { color: "red", number: 3, size: "xs" },
          { color: "red", number: 4, size: "xs" },
          { color: "red", number: 5, size: "xs" },
          { color: "red", number: 6, size: "xs", highlight: true },
        ]}
        compact
        border="#334155"
      />
      <TileGroup
        tiles={[
          { color: "blue", number: 7, size: "xs" },
          { color: "red", number: 7, size: "xs" },
          { color: "black", number: 7, size: "xs" },
          { color: "yellow", number: 7, size: "xs", highlight: true },
        ]}
        compact
        border="#334155"
      />
    </div>
  </div>

  {/* Checklist */}
  <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
    <span style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", letterSpacing: 1, marginBottom: 4 }}>DO THIS:</span>

    {[
      {
        action: "Place",
        desc: (
          <span>
            Place <Tile color="red" number={6} size="xs" highlight /> at the end of Set 1{" "}
            <span style={{ color: "#64748b" }}>(Red 3-4-5 → Red 3-4-5-<b>6</b>)</span>
          </span>
        ),
      },
      {
        action: "Place",
        desc: (
          <span>
            Place <Tile color="yellow" number={7} size="xs" highlight /> into Set 2{" "}
            <span style={{ color: "#64748b" }}>(♦7 ♥7 ♠7 → ♦7 ♥7 ♠7 <b>♣7</b>)</span>
          </span>
        ),
      },
    ].map((item, i) => (
      <div
        key={i}
        onClick={() => toggle(i)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "10px 12px",
          borderRadius: 8,
          background: checked[i] ? "#16a34a18" : "#1e293b",
          border: `1px solid ${checked[i] ? "#16a34a40" : "#334155"}`,
          cursor: "pointer",
          transition: "all 0.15s",
          textDecoration: checked[i] ? "line-through" : "none",
          opacity: checked[i] ? 0.6 : 1,
        }}
      >
        <div
          style={{
            width: 20,
            height: 20,
            borderRadius: 4,
            border: `2px solid ${checked[i] ? "#22c55e" : "#475569"}`,
            background: checked[i] ? "#22c55e" : "transparent",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 12,
            color: "#fff",
            flexShrink: 0,
          }}
        >
          {checked[i] && "✓"}
        </div>
        <span style={{ fontSize: 12, fontWeight: 600, color: "#e2e8f0", flexShrink: 0 }}>
          {i + 1}.
        </span>
        <span style={{ fontSize: 12, color: "#cbd5e1", lineHeight: 1.5 }}>{item.desc}</span>
      </div>
    ))}
  </div>
</div>
```

);
}

function Approach3_SetCentricCards() {
return (
<div style={{ display: “flex”, flexDirection: “column”, gap: 12 }}>
<div style={{ display: “flex”, gap: 8, flexWrap: “wrap” }}>
<Badge color="green">2 tiles placed</Badge>
<Badge color="blue">Optimal</Badge>
</div>

```
  {/* Each changed set gets its own card */}
  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
    {/* Card: Extended set */}
    <div
      style={{
        borderRadius: 10,
        border: "1px solid #1e40af",
        background: "linear-gradient(135deg, #1e293b 0%, #172554 100%)",
        overflow: "hidden",
      }}
    >
      <div style={{ padding: "8px 14px", display: "flex", alignItems: "center", gap: 8, borderBottom: "1px solid #1e3a5f" }}>
        <Badge color="blue">Extended</Badge>
        <span style={{ fontSize: 12, color: "#93c5fd", fontWeight: 600 }}>Set 1 — Run</span>
      </div>
      <div style={{ padding: 14, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <Tile color="red" number={3} size="sm" />
        <Tile color="red" number={4} size="sm" />
        <Tile color="red" number={5} size="sm" />
        <div style={{ width: 1, height: 28, background: "#3b82f640", margin: "0 2px" }} />
        <Tile color="red" number={6} size="sm" highlight />
        <span style={{ fontSize: 9, color: "#60a5fa", fontWeight: 600, background: "#1e40af30", padding: "2px 6px", borderRadius: 3, marginLeft: 4 }}>← FROM HAND</span>
      </div>
    </div>

    {/* Card: Extended set 2 */}
    <div
      style={{
        borderRadius: 10,
        border: "1px solid #1e40af",
        background: "linear-gradient(135deg, #1e293b 0%, #172554 100%)",
        overflow: "hidden",
      }}
    >
      <div style={{ padding: "8px 14px", display: "flex", alignItems: "center", gap: 8, borderBottom: "1px solid #1e3a5f" }}>
        <Badge color="blue">Extended</Badge>
        <span style={{ fontSize: 12, color: "#93c5fd", fontWeight: 600 }}>Set 2 — Group</span>
      </div>
      <div style={{ padding: 14, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <Tile color="blue" number={7} size="sm" />
        <Tile color="red" number={7} size="sm" />
        <Tile color="black" number={7} size="sm" />
        <div style={{ width: 1, height: 28, background: "#3b82f640", margin: "0 2px" }} />
        <Tile color="yellow" number={7} size="sm" highlight />
        <span style={{ fontSize: 9, color: "#60a5fa", fontWeight: 600, background: "#1e40af30", padding: "2px 6px", borderRadius: 3, marginLeft: 4 }}>← FROM HAND</span>
      </div>
    </div>

    {/* Unchanged sets collapsed */}
    <div style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #334155", background: "#1e293b50", display: "flex", alignItems: "center", gap: 8 }}>
      <Badge color="gray">Unchanged</Badge>
      <span style={{ fontSize: 11, color: "#64748b" }}>1 set unchanged (Set 3: Blue 10-11-12)</span>
    </div>
  </div>
</div>
```

);
}

function Approach4_TileProvenance() {
return (
<div style={{ display: “flex”, flexDirection: “column”, gap: 16 }}>
<div style={{ display: “flex”, gap: 8, flexWrap: “wrap” }}>
<Badge color="green">5 tiles placed</Badge>
<Badge color="blue">Optimal</Badge>
</div>

```
  <span style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", letterSpacing: 1 }}>RESULT BOARD — TILE ORIGINS</span>

  {/* Complex example: rearrangement */}
  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
    {/* New set from rearrangement */}
    <div style={{ borderRadius: 10, border: "1px solid #d97706", background: "#1e293b", overflow: "hidden" }}>
      <div style={{ padding: "8px 14px", display: "flex", alignItems: "center", gap: 8, borderBottom: "1px solid #92400e40" }}>
        <Badge color="amber">Rearranged</Badge>
        <span style={{ fontSize: 12, color: "#fbbf24", fontWeight: 600 }}>Set 1 — Run</span>
      </div>
      <div style={{ padding: 14, display: "flex", gap: 6, flexWrap: "wrap" }}>
        <Tile color="red" number={4} size="sm" provenance="2" />
        <Tile color="red" number={5} size="sm" provenance="2" />
        <Tile color="red" number={6} size="sm" provenance="hand" highlight />
        <Tile color="red" number={7} size="sm" provenance="3" />
      </div>
    </div>

    {/* New set */}
    <div style={{ borderRadius: 10, border: "1px solid #16a34a", background: "#1e293b", overflow: "hidden" }}>
      <div style={{ padding: "8px 14px", display: "flex", alignItems: "center", gap: 8, borderBottom: "1px solid #14532d40" }}>
        <Badge color="green">New</Badge>
        <span style={{ fontSize: 12, color: "#4ade80", fontWeight: 600 }}>Set 2 — Group</span>
      </div>
      <div style={{ padding: 14, display: "flex", gap: 6, flexWrap: "wrap" }}>
        <Tile color="blue" number={9} size="sm" provenance="hand" highlight />
        <Tile color="red" number={9} size="sm" provenance="hand" highlight />
        <Tile color="black" number={9} size="sm" provenance="hand" highlight />
      </div>
    </div>

    {/* Modified old set */}
    <div style={{ borderRadius: 10, border: "1px solid #d97706", background: "#1e293b", overflow: "hidden" }}>
      <div style={{ padding: "8px 14px", display: "flex", alignItems: "center", gap: 8, borderBottom: "1px solid #92400e40" }}>
        <Badge color="amber">Rearranged</Badge>
        <span style={{ fontSize: 12, color: "#fbbf24", fontWeight: 600 }}>Set 3 — Run</span>
        <span style={{ fontSize: 9, color: "#78350f", background: "#fbbf2420", padding: "2px 6px", borderRadius: 3, fontWeight: 600 }}>was: Red 4-5-6-7-8</span>
      </div>
      <div style={{ padding: 14, display: "flex", gap: 6, flexWrap: "wrap" }}>
        <Tile color="red" number={7} size="sm" provenance="old 3" />
        <Tile color="red" number={8} size="sm" provenance="old 3" />
        <Tile color="red" number={9} size="sm" provenance="hand" highlight />
      </div>
    </div>
  </div>

  <div style={{ fontSize: 10, color: "#64748b", padding: "6px 10px", background: "#0f172a", borderRadius: 6, border: "1px solid #1e293b" }}>
    <span style={{ color: "#22c55e", fontWeight: 700 }}>HAND</span> = from your rack &nbsp;·&nbsp;
    <span style={{ color: "#94a3b8", fontWeight: 700 }}>SET N</span> = originally from that board set
  </div>
</div>
```

);
}

function Approach5_AnimatedReplay() {
const [phase, setPhase] = useState(0);

const phases = [
{ label: “Initial State”, desc: “Board + Hand as entered” },
{ label: “Sets Break Apart”, desc: “Tiles lift from rearranged sets” },
{ label: “Tiles Recombine”, desc: “New sets form in place” },
{ label: “Final State”, desc: “All tiles settled” },
];

return (
<div style={{ display: “flex”, flexDirection: “column”, gap: 16 }}>
<div style={{ display: “flex”, gap: 8, flexWrap: “wrap” }}>
<Badge color="green">2 tiles placed</Badge>
<Badge color="purple">Animated</Badge>
</div>

```
  {/* Timeline control */}
  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
      {phases.map((p, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 4, flex: 1 }}>
          <button
            onClick={() => setPhase(i)}
            style={{
              width: 28,
              height: 28,
              borderRadius: "50%",
              border: `2px solid ${i <= phase ? "#3b82f6" : "#475569"}`,
              background: i <= phase ? "#3b82f6" : "transparent",
              color: i <= phase ? "#fff" : "#64748b",
              fontSize: 11,
              fontWeight: 700,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            {i + 1}
          </button>
          {i < phases.length - 1 && (
            <div style={{ flex: 1, height: 2, background: i < phase ? "#3b82f6" : "#334155", borderRadius: 1 }} />
          )}
        </div>
      ))}
    </div>
    <div style={{ display: "flex", justifyContent: "space-between" }}>
      {phases.map((p, i) => (
        <span key={i} style={{ fontSize: 8, color: i === phase ? "#93c5fd" : "#475569", fontWeight: 600, textAlign: "center", width: `${100 / phases.length}%`, textTransform: "uppercase", letterSpacing: 0.5 }}>
          {p.label}
        </span>
      ))}
    </div>
  </div>

  {/* Board visualization */}
  <div
    style={{
      padding: 16,
      borderRadius: 10,
      background: "#0f172a",
      border: "1px solid #1e293b",
      minHeight: 120,
      display: "flex",
      flexDirection: "column",
      gap: 8,
    }}
  >
    {phase === 0 && (
      <>
        <TileGroup
          tiles={[
            { color: "red", number: 3, size: "sm" },
            { color: "red", number: 4, size: "sm" },
            { color: "red", number: 5, size: "sm" },
          ]}
          label="Set 1"
          compact
        />
        <TileGroup
          tiles={[
            { color: "blue", number: 7, size: "sm" },
            { color: "red", number: 7, size: "sm" },
            { color: "black", number: 7, size: "sm" },
          ]}
          label="Set 2"
          compact
        />
        <div style={{ display: "flex", gap: 4, padding: "6px 8px", border: "1px dashed #475569", borderRadius: 6 }}>
          <span style={{ fontSize: 10, color: "#94a3b8", marginRight: 4 }}>HAND:</span>
          <Tile color="red" number={6} size="xs" highlight />
          <Tile color="yellow" number={7} size="xs" highlight />
        </div>
      </>
    )}
    {phase === 1 && (
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <TileGroup
          tiles={[
            { color: "red", number: 3, size: "sm" },
            { color: "red", number: 4, size: "sm" },
            { color: "red", number: 5, size: "sm" },
          ]}
          label="Set 1 — accepting tile"
          border="#3b82f650"
          compact
        />
        <div style={{ fontSize: 10, color: "#fbbf24", fontStyle: "italic", padding: "4px 8px" }}>
          ⟡ Hand tiles ready to place...
        </div>
      </div>
    )}
    {phase === 2 && (
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <TileGroup
          tiles={[
            { color: "red", number: 3, size: "sm" },
            { color: "red", number: 4, size: "sm" },
            { color: "red", number: 5, size: "sm" },
            { color: "red", number: 6, size: "sm", highlight: true },
          ]}
          label="Set 1"
          badge="+ RED 6"
          badgeColor="#16a34a"
          border="#22c55e50"
          compact
        />
        <TileGroup
          tiles={[
            { color: "blue", number: 7, size: "sm" },
            { color: "red", number: 7, size: "sm" },
            { color: "black", number: 7, size: "sm" },
            { color: "yellow", number: 7, size: "sm", highlight: true },
          ]}
          label="Set 2"
          badge="+ YELLOW 7"
          badgeColor="#16a34a"
          border="#22c55e50"
          compact
        />
      </div>
    )}
    {phase === 3 && (
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <TileGroup
          tiles={[
            { color: "red", number: 3, size: "sm" },
            { color: "red", number: 4, size: "sm" },
            { color: "red", number: 5, size: "sm" },
            { color: "red", number: 6, size: "sm", highlight: true },
          ]}
          label="Set 1"
          compact
        />
        <TileGroup
          tiles={[
            { color: "blue", number: 7, size: "sm" },
            { color: "red", number: 7, size: "sm" },
            { color: "black", number: 7, size: "sm" },
            { color: "yellow", number: 7, size: "sm", highlight: true },
          ]}
          label="Set 2"
          compact
        />
        <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 10px", background: "#16a34a18", borderRadius: 6, border: "1px solid #16a34a30" }}>
          <span style={{ fontSize: 11, color: "#4ade80", fontWeight: 600 }}>✓ All tiles placed — hand empty</span>
        </div>
      </div>
    )}
  </div>

  <div style={{ display: "flex", gap: 8 }}>
    <button
      onClick={() => setPhase((p) => Math.max(0, p - 1))}
      disabled={phase === 0}
      style={{ padding: "6px 14px", borderRadius: 6, background: "#1e293b", border: "1px solid #334155", color: phase === 0 ? "#334155" : "#94a3b8", fontSize: 12, fontWeight: 600, cursor: phase === 0 ? "not-allowed" : "pointer" }}
    >
      ◀ Back
    </button>
    <button
      onClick={() => setPhase((p) => Math.min(phases.length - 1, p + 1))}
      disabled={phase === phases.length - 1}
      style={{ padding: "6px 14px", borderRadius: 6, background: "#1e293b", border: "1px solid #334155", color: phase === phases.length - 1 ? "#334155" : "#94a3b8", fontSize: 12, fontWeight: 600, cursor: phase === phases.length - 1 ? "not-allowed" : "pointer" }}
    >
      Next ▶
    </button>
    <span style={{ fontSize: 11, color: "#475569", alignSelf: "center", fontStyle: "italic" }}>
      {phases[phase].desc}
    </span>
  </div>
</div>
```

);
}

// ═══════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════

const APPROACHES = [
{
id: “snapshot”,
num: “01”,
title: “Snapshot Diff”,
subtitle: “Before → After side-by-side”,
icon: “⬌”,
color: “#3b82f6”,
component: Approach1_SnapshotDiff,
concept:
“Show the complete board BEFORE and AFTER as two columns. No intermediate states, no fake steps. Color-code each set in the ‘after’ column to show what changed: extended (blue), new (green), rearranged (amber), unchanged (gray). Highlighted tiles = from hand.”,
pros: [
“Impossible to show invalid states — both columns are real”,
“Works at any complexity — even nightmare boards”,
“Instant comprehension for simple cases”,
“Maps directly to solver output (no post-processing needed)”,
],
cons: [
“Doesn’t explain HOW to execute rearrangements”,
“Overwhelming on 20+ set boards (needs scroll/collapse)”,
“Doesn’t guide the player’s physical actions”,
],
best: “Quick reference, simple extensions and creates. When the user just wants to see the answer, not understand the process.”,
},
{
id: “checklist”,
num: “02”,
title: “Action Checklist”,
subtitle: “Interactive to-do list of moves”,
icon: “☑”,
color: “#22c55e”,
component: Approach2_InstructionChecklist,
concept:
“Show the final board as a compact reference, then list numbered physical actions the player must take. Each action is a self-contained instruction with inline tile chips. Checkboxes let the player mark completed actions. No board state visualization at all — pure instructions.”,
pros: [
“Directly actionable — tells you exactly what to do”,
“Checkboxes give satisfying progress tracking”,
“No ambiguous ‘before’ states — instructions reference set numbers”,
“Works on mobile — just a scrollable list”,
],
cons: [
“Order of instructions matters for rearrangements but solver doesn’t guarantee valid ordering”,
“Can’t show the reasoning behind complex rearrangements”,
“Relies on set numbering which users must map to visual positions”,
],
best: “When users are physically playing a game and need step-by-step guidance. Mobile-first use case.”,
},
{
id: “setcentric”,
num: “03”,
title: “Set-Centric Cards”,
subtitle: “One card per changed set”,
icon: “▣”,
color: “#f59e0b”,
component: Approach3_SetCentricCards,
concept:
‘Show ONLY the sets that changed, each as its own card. Each card shows the FINAL state of that set with visual separators marking where new tiles were added. Unchanged sets are collapsed into a single line. The card header tells you what happened: “Extended”, “New”, “Rearranged”. Within each card, a vertical divider separates original tiles from hand tiles.’,
pros: [
“Focuses attention on what actually changed”,
“Scales well — 20 unchanged sets become 1 line”,
“Clear per-set narrative (what changed and why)”,
“The divider inside each set makes hand tiles visually obvious”,
],
cons: [
“Doesn’t show what the set USED TO look like (only the result)”,
“For rearrangements, doesn’t explain which old set was broken”,
“Cards can get tall on complex boards”,
],
best: “The sweet spot for most cases. Best default approach — focuses on what matters without fake states.”,
},
{
id: “provenance”,
num: “04”,
title: “Tile Provenance”,
subtitle: “Every tile labeled with its origin”,
icon: “◎”,
color: “#a855f7”,
component: Approach4_TileProvenance,
concept:
‘Show the FINAL board, but every tile carries a small label: “HAND” (from rack) or “SET N” (from which old board set). This makes complex rearrangements transparent: you can see that Set 1 now contains tiles from Set 2, Set 4, and your hand. For modified sets, a “was: …” annotation shows the old composition.’,
pros: [
“Most information-dense — answers ‘where did each tile come from?’”,
“Makes rearrangement chains understandable (tiles from Set 2 ended up in Set 5)”,
“Only shows ONE state (the result) — no intermediate fakes”,
“Great for complex nightmare puzzles where understanding origin is key”,
],
cons: [
“Visual clutter from labels on every tile”,
“Overkill for simple extensions where origin is obvious”,
“Requires new data from backend (per-tile origin mapping)”,
],
best: “Expert/Nightmare puzzles with deep rearrangement chains. When the user wants to UNDERSTAND the solution, not just execute it.”,
},
{
id: “replay”,
num: “05”,
title: “Animated Replay”,
subtitle: “Watch tiles move from old to new positions”,
icon: “▶”,
color: “#ec4899”,
component: Approach5_AnimatedReplay,
concept:
“Animate the transition from old board to new board. Tiles slide from their old positions to new positions. Hand tiles fly in from a ‘hand’ area. The user can scrub a timeline, pause, and replay. The animation phases are: (1) initial state, (2) sets that need modification highlight/separate, (3) tiles slide to new positions, (4) settle into final state.”,
pros: [
“Most intuitive — seeing tiles move tells the whole story”,
“Engaging and satisfying to watch”,
“Timeline scrubbing gives full control”,
“Every frame shows a visual state (not necessarily a valid game state, but an interpolation)”,
],
cons: [
“HARD to implement well — spatial layout, animation choreography, performance”,
“Intermediate animation frames are NOT valid game states”,
“Doesn’t work well on print / screenshot / screen readers”,
“Complex rearrangements become visual chaos with 15+ tiles moving simultaneously”,
],
best: “Showpiece / portfolio mode. Fun for simple cases but breaks down on complex boards. High engineering cost.”,
},
];

export default function SolutionUXProposal() {
const [activeTab, setActiveTab] = useState(“setcentric”);
const active = APPROACHES.find((a) => a.id === activeTab);

return (
<div
style={{
fontFamily: “‘Inter’, -apple-system, sans-serif”,
background: “#0b1120”,
color: “#e2e8f0”,
minHeight: “100vh”,
padding: “24px 16px”,
maxWidth: 800,
margin: “0 auto”,
}}
>
{/* Header */}
<div style={{ marginBottom: 32 }}>
<div style={{ display: “flex”, alignItems: “center”, gap: 10, marginBottom: 6 }}>
<span style={{ fontSize: 24 }}>🎯</span>
<h1 style={{ fontSize: 22, fontWeight: 800, color: “#f8fafc”, margin: 0, letterSpacing: -0.5 }}>
Solution UX Redesign
</h1>
</div>
<p style={{ fontSize: 13, color: “#64748b”, margin: 0, lineHeight: 1.6, maxWidth: 600 }}>
Five paradigms for displaying Rummikub solver results. Each approach handles the
fundamental truth differently: <em>the solver produces a final state, not a step sequence.</em>
</p>
</div>

```
  {/* Core Problem Callout */}
  <div
    style={{
      padding: "14px 18px",
      borderRadius: 10,
      background: "#7f1d1d20",
      border: "1px solid #7f1d1d60",
      marginBottom: 28,
    }}
  >
    <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
      <span style={{ fontSize: 16, flexShrink: 0 }}>⚠</span>
      <div>
        <p style={{ fontSize: 12, fontWeight: 700, color: "#fca5a5", margin: "0 0 4px" }}>
          THE ROOT PROBLEM
        </p>
        <p style={{ fontSize: 11, color: "#f87171", margin: 0, lineHeight: 1.5 }}>
          The ILP solver simultaneously rearranges the entire board. It outputs one optimal <strong>end-state</strong>,
          not a sequence of valid intermediate states. The current UI fakes intermediate steps
          by decomposing the diff — but these "steps" can't be executed in order because
          step 2 may depend on step 4's rearrangement already being done. Every "Before" state
          shown in a step is a lie.
        </p>
      </div>
    </div>
  </div>

  {/* Tab Navigation */}
  <div style={{ display: "flex", gap: 4, marginBottom: 20, overflowX: "auto", paddingBottom: 4 }}>
    {APPROACHES.map((a) => (
      <button
        key={a.id}
        onClick={() => setActiveTab(a.id)}
        style={{
          padding: "8px 14px",
          borderRadius: 8,
          border: `1px solid ${activeTab === a.id ? a.color : "#1e293b"}`,
          background: activeTab === a.id ? `${a.color}20` : "transparent",
          color: activeTab === a.id ? a.color : "#64748b",
          fontSize: 12,
          fontWeight: 700,
          cursor: "pointer",
          whiteSpace: "nowrap",
          transition: "all 0.15s",
          display: "flex",
          alignItems: "center",
          gap: 6,
        }}
      >
        <span style={{ fontSize: 14 }}>{a.icon}</span>
        {a.title}
      </button>
    ))}
  </div>

  {/* Active Approach Detail */}
  {active && (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Title + subtitle */}
      <div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
          <span style={{ fontSize: 32, fontWeight: 800, color: active.color, opacity: 0.3, fontFamily: "monospace" }}>
            {active.num}
          </span>
          <h2 style={{ fontSize: 20, fontWeight: 800, color: "#f8fafc", margin: 0 }}>{active.title}</h2>
        </div>
        <p style={{ fontSize: 13, color: "#94a3b8", margin: "4px 0 0" }}>{active.subtitle}</p>
      </div>

      {/* Concept */}
      <div style={{ padding: "14px 16px", borderRadius: 10, background: "#1e293b", border: "1px solid #334155" }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: "#64748b", letterSpacing: 1, textTransform: "uppercase" }}>
          Concept
        </span>
        <p style={{ fontSize: 12, color: "#cbd5e1", lineHeight: 1.7, margin: "6px 0 0" }}>{active.concept}</p>
      </div>

      {/* Interactive Mockup */}
      <div>
        <span style={{ fontSize: 10, fontWeight: 700, color: "#64748b", letterSpacing: 1, textTransform: "uppercase", display: "block", marginBottom: 8 }}>
          Interactive Mockup
        </span>
        <div
          style={{
            padding: 20,
            borderRadius: 12,
            background: "#0f172a",
            border: `1px solid ${active.color}30`,
          }}
        >
          <active.component />
        </div>
      </div>

      {/* Pros & Cons side by side */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div style={{ padding: "12px 14px", borderRadius: 10, background: "#16a34a10", border: "1px solid #16a34a30" }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: "#4ade80", letterSpacing: 1 }}>PROS</span>
          <ul style={{ margin: "8px 0 0", padding: "0 0 0 16px", fontSize: 11, color: "#86efac", lineHeight: 1.8, listStyleType: "'+ '" }}>
            {active.pros.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </div>
        <div style={{ padding: "12px 14px", borderRadius: 10, background: "#f8717110", border: "1px solid #f8717130" }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: "#f87171", letterSpacing: 1 }}>CONS</span>
          <ul style={{ margin: "8px 0 0", padding: "0 0 0 16px", fontSize: 11, color: "#fca5a5", lineHeight: 1.8, listStyleType: "'− '" }}>
            {active.cons.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      </div>

      {/* Best for */}
      <div style={{ padding: "10px 14px", borderRadius: 8, background: `${active.color}10`, border: `1px solid ${active.color}30` }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: active.color, letterSpacing: 1 }}>BEST FOR</span>
        <p style={{ fontSize: 12, color: "#cbd5e1", margin: "4px 0 0", lineHeight: 1.5 }}>{active.best}</p>
      </div>
    </div>
  )}

  {/* ═══════════════════════════════════════════════════════════════════ */}
  {/* RECOMMENDATION */}
  {/* ═══════════════════════════════════════════════════════════════════ */}
  <div
    style={{
      marginTop: 40,
      padding: 24,
      borderRadius: 14,
      background: "linear-gradient(135deg, #172554 0%, #1e1b4b 100%)",
      border: "1px solid #3b82f640",
    }}
  >
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
      <span style={{ fontSize: 20 }}>★</span>
      <h2 style={{ fontSize: 18, fontWeight: 800, color: "#f8fafc", margin: 0 }}>Recommendation</h2>
    </div>

    <p style={{ fontSize: 13, color: "#cbd5e1", lineHeight: 1.7, margin: "0 0 16px" }}>
      <strong style={{ color: "#fbbf24" }}>Approach 3 (Set-Centric Cards)</strong> as the default,
      with <strong style={{ color: "#a855f7" }}>Approach 4 (Tile Provenance)</strong> as an opt-in
      detail mode for complex rearrangements.
    </p>

    <div style={{ fontSize: 12, color: "#94a3b8", lineHeight: 1.7 }}>
      <p style={{ margin: "0 0 12px" }}>
        <strong style={{ color: "#e2e8f0" }}>Why not Snapshot Diff (#1)?</strong> — It's honest but passive.
        Showing two full boards forces the user to play "spot the difference" which is exactly
        the cognitive work the solver should eliminate.
      </p>
      <p style={{ margin: "0 0 12px" }}>
        <strong style={{ color: "#e2e8f0" }}>Why not Animated Replay (#5)?</strong> — Engineering cost
        is 10x the other approaches and it breaks down on complex boards. The intermediate animation
        frames are still "fake" states — just smoother fakes.
      </p>
      <p style={{ margin: "0 0 12px" }}>
        <strong style={{ color: "#e2e8f0" }}>Why Set-Centric Cards wins:</strong> It shows only what
        changed (90% noise reduction on big boards), each card is a truthful final state, and the
        per-card classification (New / Extended / Rearranged) gives instant comprehension. The
        divider within each card between "old tiles" and "new tiles" makes hand placement visually
        obvious without any labels.
      </p>
      <p style={{ margin: 0 }}>
        <strong style={{ color: "#e2e8f0" }}>Provenance as detail mode:</strong> For Expert/Nightmare
        rearrangements where tiles move between 3+ sets, add a toggle that shows Approach 4's
        origin labels on every tile. This turns the same card layout into a forensic view.
      </p>
    </div>
  </div>

  {/* ═══════════════════════════════════════════════════════════════════ */}
  {/* DATA STRUCTURE */}
  {/* ═══════════════════════════════════════════════════════════════════ */}
  <div style={{ marginTop: 32, padding: 20, borderRadius: 12, background: "#1e293b", border: "1px solid #334155" }}>
    <h2 style={{ fontSize: 16, fontWeight: 800, color: "#f8fafc", margin: "0 0 12px" }}>
      Proposed Data Model
    </h2>

    <p style={{ fontSize: 12, color: "#94a3b8", lineHeight: 1.6, margin: "0 0 16px" }}>
      The key change: instead of <code style={{ color: "#fbbf24", background: "#0f172a", padding: "1px 6px", borderRadius: 3, fontSize: 11 }}>moves[]</code> (a fake step sequence),
      the backend returns a <strong>per-set change manifest</strong>. Each entry in <code style={{ color: "#fbbf24", background: "#0f172a", padding: "1px 6px", borderRadius: 3, fontSize: 11 }}>set_changes[]</code> describes
      what happened to ONE set, with provenance data for every tile.
    </p>

    <pre
      style={{
        fontSize: 11,
        lineHeight: 1.6,
        color: "#94a3b8",
        background: "#0f172a",
        padding: 16,
        borderRadius: 8,
        overflow: "auto",
        border: "1px solid #1e293b",
        margin: 0,
      }}
    >
```

{`interface SolveResponse {
status: “solved” | “no_solution”;
tiles_placed: number;
tiles_remaining: number;
solve_time_ms: number;
is_optimal: boolean;

// NEW: replaces moves[] and new_board[]
set_changes: SetChange[];
remaining_rack: TileOutput[];
}

interface SetChange {
// What happened to this set
action: “new” | “extended” | “rearranged” | “unchanged”;

// The final state of this set (always valid)
result_set: {
type: “run” | “group”;
tiles: TileWithOrigin[];
};

// For extended/rearranged: which old set(s) contributed
// (null for “new” sets, single index for extensions,
//  multiple for rearrangements)
source_set_indices: number[] | null;

// For rearranged: what the primary source set USED to be
// (human-readable “was: Red 4-5-6-7-8”)
source_description: string | null;
}

interface TileWithOrigin {
color: TileColor | null;
number: number | null;
joker: boolean;
copy_id: number;

// NEW: where this tile came from
origin: “hand” | number;
// “hand” = from the player’s rack
// number = index of the old board set it was in
}`}
</pre>
</div>

```
  {/* ═══════════════════════════════════════════════════════════════════ */}
  {/* INTERACTION PATTERNS */}
  {/* ═══════════════════════════════════════════════════════════════════ */}
  <div style={{ marginTop: 32, padding: 20, borderRadius: 12, background: "#1e293b", border: "1px solid #334155" }}>
    <h2 style={{ fontSize: 16, fontWeight: 800, color: "#f8fafc", margin: "0 0 16px" }}>
      Interaction Patterns
    </h2>

    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {[
        {
          icon: "👆",
          title: "Tap a hand tile → highlight everywhere it appears",
          desc: "When a user taps a highlighted (hand-origin) tile in any card, pulse-highlight that same tile everywhere: in the hand section, in the result set, and in the summary count. This answers 'where did my Red 6 end up?'",
        },
        {
          icon: "📌",
          title: "Collapse unchanged sets by default",
          desc: "Show '7 sets unchanged' as a single line. Tap to expand. This is already in the current code but should be the default, not a toggle.",
        },
        {
          icon: "🔀",
          title: "Sort cards by action type, not set index",
          desc: "Show 'New' cards first (green), then 'Extended' (blue), then 'Rearranged' (amber). This groups related information and puts the most interesting changes first. Unchanged always at the bottom.",
        },
        {
          icon: "🔍",
          title: "Provenance toggle for complex solutions",
          desc: "A small toggle below the summary bar: 'Show tile origins'. When on, each tile gets a tiny label showing which old set it came from. Off by default for clean visuals, but essential for understanding nightmare-level rearrangements.",
        },
        {
          icon: "📋",
          title: "Copy as text instructions",
          desc: "A 'Copy' button that generates a numbered text list: '1. Add Red 6 to Set 1. 2. Add Yellow 7 to Set 2.' For players who want to physically execute the moves.",
        },
      ].map((p, i) => (
        <div key={i} style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
          <span style={{ fontSize: 18, flexShrink: 0 }}>{p.icon}</span>
          <div>
            <p style={{ fontSize: 12, fontWeight: 700, color: "#e2e8f0", margin: "0 0 2px" }}>{p.title}</p>
            <p style={{ fontSize: 11, color: "#94a3b8", margin: 0, lineHeight: 1.6 }}>{p.desc}</p>
          </div>
        </div>
      ))}
    </div>
  </div>

  {/* ═══════════════════════════════════════════════════════════════════ */}
  {/* MIGRATION PATH */}
  {/* ═══════════════════════════════════════════════════════════════════ */}
  <div style={{ marginTop: 32, padding: 20, borderRadius: 12, background: "#1e293b", border: "1px solid #334155", marginBottom: 32 }}>
    <h2 style={{ fontSize: 16, fontWeight: 800, color: "#f8fafc", margin: "0 0 16px" }}>
      Migration Path
    </h2>

    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {[
        {
          phase: "1",
          title: "Backend: Add origin tracking to solve()",
          desc: "After extract_solution(), map each tile in new_sets back to its old board set index (using copy_id matching). Return SetChange[] instead of moves[]. Keep moves[] for backward compat.",
          effort: "~2h",
        },
        {
          phase: "2",
          title: "Frontend: Replace SolutionView with SetChangeCards",
          desc: "One card per SetChange. Color-code by action. Show tiles with highlight for hand-origin. Collapse unchanged. Kill the step navigator entirely.",
          effort: "~3h",
        },
        {
          phase: "3",
          title: "Frontend: Add provenance toggle",
          desc: "When toggled, show small origin labels under each tile. Use the origin field from TileWithOrigin.",
          effort: "~1h",
        },
        {
          phase: "4",
          title: "Frontend: Add tile tap-to-highlight",
          desc: "Track a 'focusedTileKey' in local state. When set, highlight all instances of that (color, number, copy_id) across all cards + hand.",
          effort: "~1h",
        },
      ].map((s, i) => (
        <div key={i} style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: "50%",
              background: "#3b82f620",
              border: "1px solid #3b82f650",
              color: "#60a5fa",
              fontSize: 12,
              fontWeight: 800,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            {s.phase}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
              <p style={{ fontSize: 12, fontWeight: 700, color: "#e2e8f0", margin: 0 }}>{s.title}</p>
              <span style={{ fontSize: 10, color: "#64748b", fontWeight: 600 }}>{s.effort}</span>
            </div>
            <p style={{ fontSize: 11, color: "#94a3b8", margin: "2px 0 0", lineHeight: 1.5 }}>{s.desc}</p>
          </div>
        </div>
      ))}
    </div>
  </div>
</div>
```

);
}