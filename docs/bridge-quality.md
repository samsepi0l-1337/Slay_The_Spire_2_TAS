# Bridge validation and build boundaries

The fixture producer and game mod share `bridge/Common/MacroCommand.cs`.
Before dispatch, commands require schema version 1, a nonempty `run_id`, an
`expected_screen_id` matching the current snapshot, a supported macro type,
and its exact advertised argument set. Slots must be nonnegative integers;
missing, extra, duplicate and illegal arguments fail closed. The mod captures
current legal actions on the main thread before validation. A rejected command
logs an error and performs no dispatch. It does not emit a success acknowledgement.

`pipe-serve` binds only a loopback IP endpoint with a nonzero port. Configuration,
fixture JSON, transport and command failures report a diagnostic and exit 2.
Its next frame remains the unchanged fixture payload with an increasing sequence;
this proves transport behavior, not game action execution or acknowledgement.

The game mod opens its pipe and heartbeat only after patch-point validation and
Harmony patch application succeed. Validation checks the type and method names
listed in the versioned symbol manifest; it does not independently identify the
running game version or verify signatures. Terminal combat snapshots advertise
no actions. Act 3 clear flags require the existing visible victory-screen signal;
reaching Act 3, combat ending, dying, or finding an Architect marker is insufficient. Missing combat state emits an empty loading/menu snapshot. Named-pipe
resources belong to one connection and are disposed when it ends; deferred
commands from a disconnected connection cannot dispatch to the next peer.

Event action advertisement and dispatch share the eligible original button indices.
Locked/proceed options are omitted from selectable choices. Compact policy slots map
back to the same original option index; invalid slots are rejected, never clamped.
The previous fallback that tried a different model option after a failed click was
removed. Dialogue/proceed-only event screens retain their slot-zero navigation macro.

A normal mod build does not copy artifacts to the game directory. Intentional
local installation requires `-p:DeployMod=true`; compile-only checks should keep
it false. Game mod compilation requires the .NET 9 SDK and matching `sts2.dll`,
`GodotSharp.dll` and `0Harmony.dll` references. Fixture compilation uses .NET 8.

## Verification

```bash
python3 -m unittest discover -s bridge/tests -p 'test_*.py'
dotnet run --project bridge/tests/EventChoices/EventChoices.csproj -c Release
dotnet run --project bridge/Sts2TelemetryBridge/Sts2TelemetryBridge.csproj -c Release -- bridge-smoke
git diff --check
```

The bridge tests build the actual executable and connect over TCP. They cover
all three legal fixture macros, monotonically increasing frames, unchanged
fixture state, rejection before a next frame, and malformed/nonlocal listen
configuration. These checks do not launch the game or establish Windows named
pipe behavior. Game mod compile and live-game validation must be recorded
separately; fixture success cannot stand in for those checks.

The mod was also compiled with isolated SDK 9.0.318 against the locally installed
macOS game assemblies using `STS2DataDir=data_sts2_macos_arm64` and
`DeployMod=false`: build succeeded with zero warnings and errors. Windows pipe and
real-game event/victory behavior have not been observed by these local checks.
