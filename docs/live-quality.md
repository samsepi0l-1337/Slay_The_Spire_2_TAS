# Live transition and transport quality

`run-live` keeps one pending action and consumes it once on the next non-loading
snapshot. Loading/menu frames report waiting status without becoming a learning
transition. Frames suppressed by command cooldown cannot reuse a consumed action.
A terminal/victory frame ends the run even when no action is pending; `until_clear`
continues through early terminal frames until victory or the positive step limit.

The send callback receives `(action, expected_screen_id, run_id)` from the current
snapshot. The run id is its nonblank `extras.run_instance_id`, with seed as the
fixture/legacy fallback. `command_sender` serializes both observed identifiers in
`MacroActionCommand`;
native command sending remains gated by `--execute`. This does not establish an
execution acknowledgement: a subsequent telemetry frame is still the observable
transition boundary.

Status output creates its parent directory, and learned weights are saved when
the input stream ends, including between the 25-transition batched model saves used by
`until_clear`. Victory flags recognize the explicit true values `true`, `1`,
`"true"`, and `"1"`; malformed flags and `"false"` cannot claim completion.

The frame reader rejects a non-object payload with `ValidationError` before
advancing its sequence. `frame_stream` skips such corrupt frames and accepts the
next valid frame. TCP connection setup releases its original socket owner after
creating reader/writer streams, and closes a partial reader on setup failure.
Closing both returned streams therefore closes the connection.

Regression checks cover cooldown credit, loading-to-terminal credit, EOF weight
persistence, nested status paths, positive step limits, exact screen commands,
malformed victory flags/payloads, partial TCP setup, and a real loopback TCP EOF.
The CLI loopback test checks the serialized screen contract with no game input.
Windows/game execution remains a separate integration check.

Combat rewards compare enemy HP only for matching enemy ids/slots in the same
seed, act, floor, and combat screen (or its terminal frame). Spawned or missing
enemies are not observed damage; menu placeholders are not HP observations.
Player HP deltas remain meaningful across real combat boundaries. The reached-act-3
flag alone cannot prove victory, and a low-HP combat with only an
HP-cost card chooses legal `end_turn` instead.

Live logs append every observed transition without deleting existing records.
Only actions sent through the command callback become pending transitions; dry-run
planning sends no commands and does not update the model or create transitions.
Pending actions reset when seed or `extras.run_instance_id` changes. Legacy frames
without a run id retain seed-based identity. `extras.player_authoritative=false`
prevents placeholder player values from contributing rewards or TD updates.

TCP accepts bracketed IPv6 endpoints such as `tcp:[::1]:9902`; brackets delimit
the host in the endpoint and are removed before socket address resolution.

The CLI loopback server allows 30 seconds for the first command, matching the
transport connection budget. Cold Torch optimizer/policy startup can exceed the
former 2-second receive timeout; command, screen, and thread-completion assertions
remain unchanged. The separate stream-close test has no policy startup.
