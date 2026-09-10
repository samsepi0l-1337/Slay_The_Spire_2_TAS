using System.Reflection;
using System.Text.Json;

namespace Sts2TasMod;

public static class PatchPoints
{
    public static void AssertPresent()
    {
        var assembly = typeof(MegaCrit.Sts2.Core.Combat.CombatManager).Assembly;
        foreach (var (key, symbol) in RequiredSymbols())
        {
            if (!Resolve(assembly, symbol))
            {
                throw new InvalidOperationException($"missing patch point {key}: {symbol}");
            }
        }
    }

    internal static IEnumerable<KeyValuePair<string, string>> RequiredSymbols()
    {
        yield return new("combat_manager", "MegaCrit.Sts2.Core.Combat.CombatManager");
        yield return new("combat_state_tracker", "MegaCrit.Sts2.Core.Combat.CombatStateTracker");
        yield return new("play_card_action", "MegaCrit.Sts2.Core.GameActions.PlayCardAction");
        yield return new("player_cmd", "MegaCrit.Sts2.Core.Commands.PlayerCmd");
        yield return new("run_manager", "MegaCrit.Sts2.Core.Runs.RunManager");
    }

    internal static bool Resolve(Assembly assembly, string symbol)
    {
        var typeName = symbol;
        var method = "";
        var lastDot = symbol.LastIndexOf('.');
        if (lastDot > 0 && assembly.GetType(symbol) is null)
        {
            typeName = symbol[..lastDot];
            method = symbol[(lastDot + 1)..];
        }
        var type = assembly.GetType(typeName) ?? Type.GetType(typeName);
        if (type is null)
        {
            return false;
        }
        if (method.Length == 0)
        {
            return true;
        }
        return type.GetMember(method, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static).Length > 0;
    }

    public static string Describe()
    {
        return JsonSerializer.Serialize(new
        {
            game_version = "v0.107.1",
            fail_closed = true,
            pipe_name = ModEntry.PipeName,
            symbols = RequiredSymbols().ToDictionary(pair => pair.Key, pair => pair.Value)
        });
    }
}
