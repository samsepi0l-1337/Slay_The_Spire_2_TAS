# ML artifact and demonstration boundaries

BC and Q* artifacts use JSON for `.json` paths and CPU Torch checkpoints for
other paths. Torch checkpoints load with `weights_only=True`; arbitrary pickle
callbacks are rejected without execution. The PPO smoke artifact uses the same
restricted Torch loading mode and remains BC smoke training, not PPO training.

BC validates each demonstration before training or writing a model. States must
be objects, legal actions must be lists, and the chosen macro must be among the
legal actions. Terminal rows without legal actions are skipped for training and
evaluation. An empty or terminal-only training dataset raises
`ValueError("no actionable demonstrations")` and preserves any existing model.

BC inference uses the stored linear weights directly. BC training and Q* model
initialization seed a temporary CPU RNG scope, preserving the caller's RNG state
and giving repeatable initial weights.

Q* restores compatible checkpoint weights and update counts. Feature dimension,
feature version, or hidden size mismatches reset the complete model and update
count. A malformed state dictionary also resets the complete model, discarding
any tensors copied before Torch reported the mismatch. Legacy artifacts without
metadata retain their previous shape-based compatibility behavior.

Regression coverage lives in `tests/test_ml_quality.py`, including harmless
pickle callbacks, RNG preservation, invalid datasets, and complete checkpoint
reset. Fixture CLI and Q* episode tests cover artifact persistence end to end.
