# Core quality corrections

## Snapshot ownership and environment reset

`TelemetrySnapshot.from_dict()` captures nested input data independently, and
`to_dict()` exports an independent tree. Environment simulation therefore keeps
the source telemetry, previously logged state and sibling Q* search branches
unchanged. `Sts2Env` stores its own initial snapshot; each `reset(seed=...)`
restores the initial observation and legal action space. The seed remains reset
metadata: fixture draw order is deterministic and this adapter does not
implement seeded game generation.

## Input boundary

Telemetry object fields, entity-list entries and macro actions reject invalid
shapes with `ValidationError`. Timestamps must be finite numeric values; boolean
values are rejected. Macro arguments must match the action shape, including the
optional `target_slot` for `play_card`. Consumed optional card `cost`, `damage`
and `block` fields in all four piles, enemy `hp`/`block`/`slot`,
`player.resources.stars` and `extras.ascension` must be integers when present.
`player.resources` must be an object when present. Missing optional fields
retain their existing defaults, and integer cost sentinels remain accepted.
Enemy `id` must be a string when present so encounter reward identity remains
hashable; missing enemy identity fields retain their existing defaults.
Existing required fields, nonnegative integer slots and snapshot choice bounds remain enforced.

Action indices accept integer policy outputs, including NumPy integers, while
rejecting booleans, floating-point values and nonnumeric objects before state
mutation. Combat masks keep zero-damage skills untargeted even when the bridge
always emits a `damage` field, while zero-damage attacks remain targeted.
Oversized numeric timestamps that cannot convert to a finite float are rejected
with `ValidationError`, preserving corrupt-frame handling.

## Execution boundary

`MacroExecutor.plan()` remains a dry-run planner. `execute()` requires explicit
`--execute` authorization and then raises `NotImplementedError`, because no native
input backend exists in this class. It cannot report an acknowledgement without
executing input. Live bridge command sending is a separate transport boundary;
this correction does not remove its command sender.

## Regression evidence

- New core regressions before implementation: 19 failed, 2 passed.
- Entity-list boundary regressions before implementation: 5 failed, 21 passed.
- Independent environment action capture before correction: 1 failed, 28 passed.
- Targeted tests cover source/export isolation, episode reset, integer indices,
  malformed objects and timestamps, argument shape and the execution gate.
- Initial core runtime/schema/quality checks: 50 passed.
- Zero-damage targeting and oversized timestamp regression: 2 failed before
  correction; final focused core checks: 52 passed.
- Full suite before caller integration: 93 passed, 1 expected Q* execute
  regression failure; all core modules had 100% statement coverage. The one
  uncovered statement was the Q* return after the unavailable execute backend.
- Nested consumed-field regressions: 14 failed, 1 passed before correction;
  focused core tests: 67 passed after correction. Full pre-integration suite:
  111 passed with the same Q* execute expectation failure; core coverage 100%.
  The frame reader also verifies that rejected values do not advance sequence.
- Enemy identity regressions: 4 failed, 16 passed before correction; 20 passed
  after correction. Integrated full suite: 178 passed, 16 subtests passed;
  100.00% Python statement coverage. Pinned Ruff lint and format checks passed.
- Existing core tests are split into runtime and schema files to stay below the
  repository's 400-line file limit.

Windows SSH verification and merged CLI/Q* integration checks belong to the
coordinator. This document does not claim observed native input or live-game
acknowledgement.
