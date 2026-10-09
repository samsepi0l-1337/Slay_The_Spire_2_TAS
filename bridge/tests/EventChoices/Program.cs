using Sts2Bridge;

var indices = EventChoices.EligibleIndices([(true, false), (false, false), (false, false), (false, true)]);
if (!indices.SequenceEqual([1, 2]))
    throw new Exception("Locked/proceed options must not shift eligible choice identity");
if (EventChoices.EligibleIndices([(true, false), (false, true)]).Length != 0)
    throw new Exception("A navigation-only screen must not advertise a locked event choice");
if (EventChoices.EligibleIndices([]).Length != 0)
    throw new Exception("An empty event must have no selectable option indices");
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
