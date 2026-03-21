"use client";

export default function RulesPanel() {
  return (
    <details className="rounded-lg border border-gray-200 overflow-hidden text-sm">
      <summary className="px-4 py-2 cursor-pointer font-medium text-gray-600 hover:bg-gray-50 select-none list-none flex items-center gap-2">
        <span className="text-base">ℹ</span> How sets work
      </summary>
      <div className="px-4 py-3 space-y-3 text-gray-600 bg-gray-50 border-t border-gray-200">

        <div>
          <p className="font-semibold text-gray-700">Run</p>
          <p>3–13 tiles of the <strong>same color</strong>, in consecutive numbers (1–13).
          Jokers fill gaps.</p>
          <p className="text-xs text-gray-400 mt-0.5">e.g. Red 5 · Red 6 · Red 7</p>
        </div>

        <div>
          <p className="font-semibold text-gray-700">Group</p>
          <p>3–4 tiles with the <strong>same number</strong>, each a different color.
          Jokers substitute missing colors.</p>
          <p className="text-xs text-gray-400 mt-0.5">e.g. Red 8 · Blue 8 · Black 8</p>
        </div>

        <div>
          <p className="font-semibold text-gray-700">First turn</p>
          <p>Your initial meld must total <strong>≥ 30 points</strong> (sum of face
          values of placed tiles). Board tiles may not be reused.</p>
        </div>

        <div>
          <p className="font-semibold text-gray-700">Joker</p>
          <p>Substitutes any tile. Its value equals the tile it represents.
          You may retrieve a joker from the board by replacing it with the matching tile.</p>
        </div>

      </div>
    </details>
  );
}
