A simple stacker game (i.e. a Tetris clone) created in python.
Requires PIL, arcade, and numpy packages

Piece sequence uses a queue which is filled by a randomly sampled bag without replacement,
therefore each piece will appear exactly once over an iteration of seven pieces.

Score depends on number of lines cleared, combos, and back-to-back 4-liners. 
No screen clears or spin bonuses are applied.
