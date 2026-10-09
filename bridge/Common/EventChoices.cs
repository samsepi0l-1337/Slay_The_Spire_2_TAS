namespace Sts2Bridge;

public static class EventChoices
{
    public static int[] EligibleIndices(IEnumerable<(bool Locked, bool Proceed)> options)
    {
        return options.Select((option, index) => (option, index))
            .Where(pair => !pair.option.Locked && !pair.option.Proceed)
            .Select(pair => pair.index).ToArray();
    }
    public static int AdvertisedCount(IEnumerable<(bool Locked, bool Proceed)> options, bool navigationAvailable)
    {
        var count = EligibleIndices(options).Length;
        return count == 0 && navigationAvailable ? 1 : count;
    }
}
