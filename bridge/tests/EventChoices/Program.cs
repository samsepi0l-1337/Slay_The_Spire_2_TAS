using Sts2Bridge;
using System.Text.Json;

var indices = EventChoices.EligibleIndices([(true, false), (false, false), (false, false), (false, true)]);
if (!indices.SequenceEqual([1, 2]))
    throw new Exception("Locked/proceed options must not shift eligible choice identity");
if (EventChoices.EligibleIndices([(true, false), (false, true)]).Length != 0)
    throw new Exception("A navigation-only screen must not advertise a locked event choice");
if (EventChoices.EligibleIndices([]).Length != 0)
    throw new Exception("An empty event must have no selectable option indices");
if (EventChoices.AdvertisedCount([(true, false), (true, false)], false) != 0)
    throw new Exception("All locked options without navigation must advertise no command");
if (EventChoices.AdvertisedCount([(true, false)], true) != 1)
    throw new Exception("An actual dialogue/proceed control permits one navigation command");
if (EventChoices.AdvertisedCount([(true, false), (false, false), (false, false)], true) != 2)
    throw new Exception("Navigation availability must not add a synthetic slot to real choices");
Console.WriteLine("Event choice eligibility: PASS");

var firstRun = new object();
var secondRun = new object();
if (RunIdentity.For(firstRun) != RunIdentity.For(firstRun))
    throw new Exception("A run identity must remain stable across snapshots");
if (RunIdentity.For(firstRun) == RunIdentity.For(secondRun))
    throw new Exception("A new run object must have a distinct identity even with a repeated game seed");
if (RunIdentity.For(null) is not null)
    throw new Exception("No run must not fabricate an identity");
Console.WriteLine("Run instance identity: PASS");

var currentSnapshot = Snapshot(new { run_instance_id = "current-run" });
MacroCommand.Validate(Command("current-run"), currentSnapshot);
try
{
    MacroCommand.Validate(Command("previous-run"), currentSnapshot);
    throw new Exception("A stale run command must be rejected even with the same screen and macro");
}
catch (InvalidOperationException error) when (error.Message.Contains("run_id")) { }
foreach (var extras in new object?[] { null, new { run_instance_id = (string?)null }, new { run_instance_id = "" }, new { run_instance_id = "  " }, new { run_instance_id = 42 } })
{
    MacroCommand.Validate(Command("seed-1"), Snapshot(extras));
}
Console.WriteLine("Macro command run binding: PASS");

static JsonElement Snapshot(object? extras) => JsonSerializer.SerializeToElement(new
{
    seed = "seed-1",
    screen_id = "combat-1",
    extras,
    valid_actions = new[] { new { action_type = "end_turn", args = new Dictionary<string, int>() } }
});

static string Command(string runId) => JsonSerializer.Serialize(new
{
    run_id = runId,
    schema_version = 1,
    expected_screen_id = "combat-1",
    action = new { action_type = "end_turn", args = new Dictionary<string, int>() }
});
