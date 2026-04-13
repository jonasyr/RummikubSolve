• The smartest next step is not more generator work. It’s to start collecting usable calibration data with the telemetry foundation you now have.

  Do this now

  1. Verify telemetry is being written during real play.

  - load a few puzzles in play mode
  - solve some of them
  - confirm telemetry_events gets:
      - puzzle_loaded
      - move/undo events
      - puzzle_solved

  2. Add one small export script next.

  - this is the highest-leverage code change now
  - build backend/solver/generator/export_telemetry.py
  - export CSV from telemetry_events
  - include:
      - event_type
      - puzzle_id
      - difficulty
      - generator_version
      - all v2 metrics
      - elapsed_ms
      - move_count
      - undo_count
      - redo_count
      - commit_count
      - revert_count

  3. Then generate and solve puzzles manually.

  - yes, this is the correct next calibration activity
  - do not retune weights blindly from generated metrics alone
  - you need human solve outcomes against those metrics

  Recommended first calibration batch

  - 5 easy
  - 5 medium
  - 5 hard
  - 5 expert
  - 5 nightmare

  Use fixed seeds and keep them recorded.

  What you should analyze first

  - solved-event elapsed_ms by requested tier
  - average undo_count by tier
  - average composite_score by tier
  - whether higher composite_score broadly means more time and more undoing

  What not to do yet

  - do not re-enable tier gating yet
  - do not regenerate pools yet
  - do not keep changing weights by intuition every few puzzles
  - do not build full regression/calibration code before you have at least a small dataset

  Best order from here

  1. export script
  2. collect 25 solved runs
  3. inspect CSV manually
  4. make first small difficulty_weights.json adjustment
  5. rerun the same seed set
  6. compare before/after
  7. only after that, consider a calibrate.py helper

  Practical rule

  - if you want the fastest path to useful progress: write the export script, then solve puzzles
  - if you want the fastest path to “more code”: don’t; that’s lower value right now than getting real calibration data

  So the answer is: one small code change for export, then generate puzzles and solve them. That is the highest-signal next move.
