"""Template T1: Joker Displacement Chain.

Structural guarantee
--------------------
Exactly one joker is embedded in a 4-colour group on the board.  The rack
contains the tile the joker substitutes for (the *trigger*, the 4th-colour
tile) plus two *completer* tiles that form a new group only after the cascade
resolves.

Chain construction (chain_depth = 3)
--------------------------------------
Four colours are used: C (chain), X, Y, Z.

Board:
  S0  GRP  [C(n+2)[0], X(n+2)[0], Y(n+2)[0], JOKER(≡Z(n+2))]
  S1  RUN  [C(n+1)[0], C(n+2)[1], C(n+3)[0]]
  Bx  RUN  [X(n+1)[0], X(n+2)[1], X(n+3)[1]]  ← blocks X completer; gives 2nd home
  By  RUN  [Y(n+1)[0], Y(n+2)[1], Y(n+3)[1]]  ← blocks Y completer; gives 2nd home
  D1  GRP  [C(1)[0],   X(1)[0],   Y(1)[0]]    ← low distractor
  D2  RUN  [Z(1)[0],   Z(2)[0],   Z(3)[0]]    ← Z-colour low distractor
  D3  RUN  [Z(11)[0],  Z(12)[0],  Z(13)[0]]   ← Z-colour high distractor

Rack: [Z(n+2)[0], X(n+3)[0], Y(n+3)[0]]

Intended ILP path:
  1. Place Z(n+2)[0] in S0 → new_A = GROUP [C(n+2)[0], X(n+2)[0], Y(n+2)[0],
     Z(n+2)[0]].  Joker freed.
  2. Joker → S1, replacing C(n+3)[0] → new_B = RUN [C(n+1)[0], C(n+2)[1],
     JOKER(≡C(n+3))].  C(n+3)[0] freed.
  3. C(n+3)[0] + X(n+3)[0] + Y(n+3)[0] → new_C = GROUP [C(n+3), X(n+3), Y(n+3)].

DAG: new_A → new_B → new_C  ⟹  chain_depth = 3.

Why the trigger Z(n+2)[0] has no trivial extension home
---------------------------------------------------------
S0 is a full 4-colour group (maximum size for groups).  Appending any tile
creates a 5-tile group, which is always invalid.  All other board sets either
use a different colour, a different number, or are in Z-colour at numbers far
from n+2 — none accept Z(n+2)[0] as a valid extension.

Why the heuristic solver fails
--------------------------------
The trigger Z(n+2)[0] has no trivial home (S0 is at max group capacity).
The heuristic never attempts joker displacement, so it cannot free C(n+3)[0].
Without C(n+3)[0] the group new_C cannot form, so the completer tiles also
cannot be placed.

Why the puzzle is unique
--------------------------
• Z(n+2)[0] can only replace JOKER in S0 — its sole valid destination is the
  4-colour group completion; all other candidates either yield wrong numbers,
  wrong colours, or over-capacity sets.
• Once S0 is fixed, the joker must go to S1 (the only set where substituting
  for a tile keeps the set valid without creating a duplicate).
• C(n+3)[0] freed from S1 has only one valid home: new_C as the chain-colour
  member.
• Completers X(n+3)[0] and Y(n+3)[0] are copy-blocked by their blocker runs
  and can only join new_C.

See PUZZLE_GENERATION_REBUILD_PLAN.md §7 Phase C and issue #38.
"""
from __future__ import annotations

__all__ = ["T1JokerDisplacementV1"]

import random

from solver.generator.templates import register_template
from solver.generator.templates.base import Template, TemplateInstance
from solver.models.tile import Color, Tile
from solver.models.tileset import SetType, TileSet

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALL_COLORS: list[Color] = list(Color)


def _run(color: Color, start: int, end: int) -> TileSet:
    """Create a run TileSet with copy_id=0 for all tiles."""
    tiles = [Tile(color=color, number=n, copy_id=0) for n in range(start, end + 1)]
    return TileSet(type=SetType.RUN, tiles=tiles)


def _group(number: int, colors: list[Color]) -> TileSet:
    """Create a group TileSet with copy_id=0 for all tiles."""
    tiles = [Tile(color=c, number=number, copy_id=0) for c in colors]
    return TileSet(type=SetType.GROUP, tiles=tiles)


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------


@register_template
class T1JokerDisplacementV1(Template):
    """Joker displacement chain template — expert tier.

    Structural invariants
    ---------------------
    * Exactly 1 joker on the board (in S0, a 4-colour group).
    * Rack size = 3: trigger + two completers.
    * chain_depth ≥ 3 by construction (verified by ILP gate).
    * No rack tile has a trivial extension home — S0 is at max group capacity
      (4 tiles), so appending any 5th tile is always invalid.
    * Joker is displaced in every valid solution (post-ILP gate).

    Uniqueness argument
    -------------------
    The trigger tile Z(n+2)[0] has only one valid full-board placement: the
    joker slot in S0, completing the 4-colour group.  Once S0 is resolved the
    cascade is forced: the joker has exactly one valid destination (S1), and
    the freed C(n+3)[0] tile has exactly one valid group (new_C with the two
    completer tiles).

    Why not trivial
    ---------------
    The heuristic solver (HeuristicSolver) does not attempt joker
    displacement.  The trigger tile has zero trivial homes (S0 is at
    4-tile group capacity; Rule 1 fails).  Single-set breaks (Rules 3–4)
    cannot expose the trigger's slot because breaking any non-S0 set leaves
    the trigger with no valid home.

    Expected rejection rates (per 100 seeds, 10 attempts each)
    ------------------------------------------------------------
    * trivial_extension gate:  ~0 %  (4-colour group blocks all extensions)
    * single_home gate:        ~0 %  (blocker runs provide 2nd homes)
    * not_unique gate:         ~5–15 %  (rarely a distractor enables alt path)
    * heuristic_solved gate:   ~0 %  (no trivial path exists by design)
    * Overall success rate:    ≥ 80 %

    Known failure modes
    -------------------
    * If `n + 2 >= 10` the trigger tile is adjacent to D3 (Z-colour 11-13),
      enabling a trivial extension.  Mitigated by clamping n to {3..7}
      so n+2 ≤ 9 and n+3 ≤ 10 (blocker runs stay within 1-13).
    * Distractor sets that share colour+number adjacency with rack tiles
      can open trivial extension paths.  Z-colour distractors use numbers
      1–3 and 11–13, always non-adjacent to the chain range n+1..n+3.
    """

    template_id = "T1_joker_displacement_v1"
    template_version = "1"
    tier = "expert"

    def generate(self, rng: random.Random) -> TemplateInstance:
        """Construct one T1 puzzle instance.

        Parameters
        ----------
        rng:
            Pre-seeded :class:`random.Random`.  Must be the *sole* source
            of randomness.

        Returns
        -------
        :class:`TemplateInstance`
            Board + rack ready for gate evaluation.
        """
        # ------------------------------------------------------------------
        # 1. Choose chain parameters
        # ------------------------------------------------------------------
        color_c: Color = rng.choice(_ALL_COLORS)
        # n ∈ {3..7}: ensures n+2 ≤ 9 (trigger non-adjacent to D3 at 11-13)
        # and n+3 ≤ 10 (blocker runs stay within valid tile numbers 1-13).
        # n=8 is excluded because n+2=10 is adjacent to D3 start (11), enabling
        # a trivial extension of the trigger into D3.
        n: int = rng.randint(3, 7)

        other_colors = [c for c in _ALL_COLORS if c != color_c]
        # color_x, color_y: two colours for the completer tiles and blocker runs.
        color_x, color_y = rng.sample(other_colors, 2)
        # color_z: the 4th colour — the joker acts as Z(n+2) in S0, and the
        # rack trigger is Z(n+2)[0].
        color_z = next(c for c in other_colors if c not in (color_x, color_y))

        # ------------------------------------------------------------------
        # 2. S0: 4-colour group containing the joker
        #
        # GROUP [C(n+2)[0], X(n+2)[0], Y(n+2)[0], JOKER(≡Z(n+2))]
        #
        # Groups are capped at 4 tiles.  Appending ANY rack tile would create
        # a 5-tile group → always invalid.  This unconditionally blocks all
        # trivial extension paths for all three rack tiles.
        # ------------------------------------------------------------------
        s0 = TileSet(
            type=SetType.GROUP,
            tiles=[
                Tile(color=color_c, number=n + 2, copy_id=0),
                Tile(color=color_x, number=n + 2, copy_id=0),
                Tile(color=color_y, number=n + 2, copy_id=0),
                Tile.joker(copy_id=0),
            ],
        )

        # ------------------------------------------------------------------
        # 3. S1: C-colour run — the joker displaces C(n+3)[0] here
        #
        # RUN [C(n+1)[0], C(n+2)[1], C(n+3)[0]]
        #
        # C(n+2)[1] is the second copy (first copy C(n+2)[0] is in S0).
        # C(n+3)[0] is the only copy on the board; the freed C(n+3)[0] will
        # become the chain-colour member of new_C.
        # ------------------------------------------------------------------
        s1 = TileSet(
            type=SetType.RUN,
            tiles=[
                Tile(color=color_c, number=n + 1, copy_id=0),
                Tile(color=color_c, number=n + 2, copy_id=1),  # 2nd copy; S0 has [0]
                Tile(color=color_c, number=n + 3, copy_id=0),
            ],
        )

        # ------------------------------------------------------------------
        # 4. Blocker runs for the completer tiles
        #
        # Each blocker run:
        #   • Contains copy_id=1 of the matching completer tile → appending
        #     copy_id=0 from rack creates a duplicate → trivial ext blocked.
        #   • Also provides a second candidate home for the completer tile in
        #     enumerate_valid_sets (the full run [X(n+1), X(n+2), X(n+3)] is
        #     a valid set that can be assembled from board + rack tiles).
        #
        # X(n+2)[1] / Y(n+2)[1]: second copies (first copies are in S0).
        # ------------------------------------------------------------------
        blocker_x = TileSet(
            type=SetType.RUN,
            tiles=[
                Tile(color=color_x, number=n + 1, copy_id=0),
                Tile(color=color_x, number=n + 2, copy_id=1),  # 2nd copy; S0 has [0]
                Tile(color=color_x, number=n + 3, copy_id=1),  # blocks X(n+3)[0] from rack
            ],
        )

        blocker_y = TileSet(
            type=SetType.RUN,
            tiles=[
                Tile(color=color_y, number=n + 1, copy_id=0),
                Tile(color=color_y, number=n + 2, copy_id=1),  # 2nd copy; S0 has [0]
                Tile(color=color_y, number=n + 3, copy_id=1),  # blocks Y(n+3)[0] from rack
            ],
        )

        # ------------------------------------------------------------------
        # 5. Distractor sets
        #
        # Use numbers far from the chain range [n+1..n+3] to avoid accidental
        # trivial-extension paths.  The trigger Z(n+2)[0] has n+2 ∈ {5..10};
        # distractors in Z-colour use 1–3 (always < n+1) and 11–13 (always >
        # n+3 ≤ 11), so the trigger can never consecutively extend them.
        #
        # D1: low 3-colour group at 1 (chain-colour, X, Y)
        # D2: Z-colour run at 1–3  (Z is the trigger colour)
        # D3: Z-colour run at 11–13
        #
        # All distractor tiles are copy_id=0 (they appear nowhere else).
        # ------------------------------------------------------------------
        d1 = _group(1, [color_c, color_x, color_y])
        d2 = _run(color_z, 1, 3)
        d3 = _run(color_z, 11, 13)

        # ------------------------------------------------------------------
        # 6. Assemble board and rack
        # ------------------------------------------------------------------
        board_sets: list[TileSet] = [s0, s1, blocker_x, blocker_y, d1, d2, d3]

        rack: list[Tile] = [
            Tile(color=color_z, number=n + 2, copy_id=0),  # trigger: replaces JOKER in S0
            Tile(color=color_x, number=n + 3, copy_id=0),  # completer X
            Tile(color=color_y, number=n + 3, copy_id=0),  # completer Y
        ]

        return TemplateInstance(
            template_id=self.template_id,
            template_version=self.template_version,
            tier=self.tier,
            board_sets=board_sets,
            rack=rack,
            declared_chain_depth=3,
            declared_disruption_min=8,
            construction_notes={
                "chain_color": color_c.value,
                "color_x": color_x.value,
                "color_y": color_y.value,
                "color_z": color_z.value,
                "base_n": n,
                "joker_substitutes": f"{color_z.value}:{n + 2}",
            },
        )
