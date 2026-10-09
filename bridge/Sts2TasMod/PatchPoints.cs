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
        yield return new("mod_initializer", "MegaCrit.Sts2.Core.Modding.ModInitializerAttribute");
        yield return new("combat_state", "MegaCrit.Sts2.Core.Combat.CombatState");
        yield return new("combat_manager", "MegaCrit.Sts2.Core.Combat.CombatManager");
        yield return new("combat_state_tracker", "MegaCrit.Sts2.Core.Combat.CombatStateTracker");
        yield return new("notify_combat_state_changed", "MegaCrit.Sts2.Core.Combat.CombatStateTracker.NotifyCombatStateChanged");
        yield return new("play_card_action", "MegaCrit.Sts2.Core.GameActions.PlayCardAction");
        yield return new("player_cmd_end_turn", "MegaCrit.Sts2.Core.Commands.PlayerCmd.EndTurn");
        yield return new("action_queue_synchronizer", "MegaCrit.Sts2.Core.GameActions.Multiplayer.ActionQueueSynchronizer.RequestEnqueue");
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
        return type.GetMethods(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static).Any(candidate => candidate.Name == method);
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
