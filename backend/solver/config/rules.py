from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RulesConfig:
    """Configurable Rummikub rule variants that affect solver behaviour.

    All fields use the most common tournament/standard defaults.
    Pass a custom instance to the solver to enable variant rules.

    initial_meld_threshold:
        Minimum total point value (sum of tile face values) a player
        must place on their very first turn. Standard: 30 points.

    is_first_turn:
        When True, the solver enforces the initial_meld_threshold and
        disallows using tiles already on the board.

    allow_wrap_runs:
        When True, runs may wrap around (e.g. 12-13-1 is valid).
        Standard rules: False (no wrap-around).

    joker_retrieval:
        When True, a player may swap a face tile for a joker already
        placed on the board, freeing the joker for use elsewhere.
        Standard rules: True.
        NOTE: accepted in config for forward-compatibility but not yet
        implemented in the ILP formulation — setting it to False has no
        effect on solver behaviour.
    """

    initial_meld_threshold: int = 30
    is_first_turn: bool = False
    allow_wrap_runs: bool = False
    joker_retrieval: bool = True  # TODO: implement in ILP formulation
