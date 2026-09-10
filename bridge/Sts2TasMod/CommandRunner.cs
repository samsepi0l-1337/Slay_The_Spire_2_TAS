using System.Text.Json;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.GameActions;
using Godot;
using MegaCrit.Sts2.Core.Runs;

namespace Sts2TasMod;

public static class CommandRunner
{
    public static void Apply(string line)
    {
        try
        {
            using var document = JsonDocument.Parse(line);
            var root = document.RootElement;
            if (!root.TryGetProperty("action", out var action))
            {
                PipeHub.WriteSnapshot();
                return;
            }
            var actionType = action.GetProperty("action_type").GetString();
            var args = action.TryGetProperty("args", out var rawArgs) ? rawArgs : default;
            if (actionType == "end_turn")
            {
                EndTurn();
            }
            else if (actionType == "play_card")
            {
                PlayCard(ReadInt(args, "hand_slot"), ReadInt(args, "target_slot"));
            }
            PipeHub.WriteSnapshot();
        }
        catch (Exception ex)
        {
            GD.PrintErr($"Sts2TasMod command failed closed: {ex.Message}");
        }
    }

    private static void EndTurn()
    {
        var player = LocalPlayer();
        if (player is null)
        {
            throw new InvalidOperationException("no local player");
        }
        PlayerCmd.EndTurn(player, false);
    }

    private static void PlayCard(int? handSlot, int? targetSlot)
    {
        if (handSlot is null)
        {
            throw new InvalidOperationException("play_card missing hand_slot");
        }
        var player = LocalPlayer();
        var state = CombatManager.Instance.DebugOnlyGetState();
        if (player?.PlayerCombatState is null || state is null)
        {
            throw new InvalidOperationException("not in combat");
        }
        var cards = player.PlayerCombatState.Hand.Cards;
        if (handSlot.Value < 0 || handSlot.Value >= cards.Count)
        {
            throw new InvalidOperationException("hand_slot out of range");
        }
        var card = cards[handSlot.Value];
        var target = targetSlot is null ? null : state.HittableEnemies.ElementAtOrDefault(targetSlot.Value);
        var action = new PlayCardAction(card, target);
        RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(action);
    }

    private static MegaCrit.Sts2.Core.Entities.Players.Player? LocalPlayer()
    {
        var state = CombatManager.Instance.DebugOnlyGetState();
        return state?.Players.Count > 0 ? state.Players[0] : null;
    }

    private static int? ReadInt(JsonElement args, string key)
    {
        if (args.ValueKind != JsonValueKind.Object || !args.TryGetProperty(key, out var value) || value.ValueKind != JsonValueKind.Number)
        {
            return null;
        }
        return value.GetInt32();
    }
}
