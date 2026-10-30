using System.Runtime.CompilerServices;

namespace Sts2Bridge;

public static class RunIdentity
{
    private static readonly ConditionalWeakTable<object, string> Ids = new();

    public static string? For(object? run)
    {
        return run is null ? null : Ids.GetValue(run, _ => Guid.NewGuid().ToString("N"));
    }
}
