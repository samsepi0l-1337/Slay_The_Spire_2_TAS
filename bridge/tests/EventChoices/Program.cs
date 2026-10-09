using Sts2Bridge;

var indices = EventChoices.EligibleIndices([(true, false), (false, false), (false, false), (false, true)]);
if (!indices.SequenceEqual([1, 2]))
    throw new Exception("Locked/proceed options must not shift eligible choice identity");
if (EventChoices.EligibleIndices([(true, false), (false, true)]).Length != 0)
    throw new Exception("A navigation-only screen must not advertise a locked event choice");
if (EventChoices.EligibleIndices([]).Length != 0)
    throw new Exception("An empty event must have no selectable option indices");
Console.WriteLine("Event choice eligibility: PASS");
