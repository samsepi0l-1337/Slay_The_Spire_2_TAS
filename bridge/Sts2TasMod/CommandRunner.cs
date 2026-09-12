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
            GD.Print($"Sts2TasMod command {actionType}");
            if (actionType == "end_turn")
            {
                EndTurn();
            }
            else if (actionType == "play_card")
            {
                PlayCard(ReadInt(args, "hand_slot"), ReadInt(args, "target_slot"));
            }
            else if (actionType is "choose_map_node" or "choose_reward" or "choose_event_option" or "shop_buy" or "shop_remove")
            {
                RunFlow.Apply(actionType, ReadInt(args, "node_slot") ?? ReadInt(args, "choice_slot") ?? ReadInt(args, "item_slot") ?? ReadInt(args, "card_slot"));
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
        if (!card.CanPlay(out var reason, out _))
        {
            throw new InvalidOperationException($"cannot play {card.Id.Entry}: {reason}");
        }
        var action = new PlayCardAction(card, target);
        RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(action);
        GD.Print($"Sts2TasMod play_card slot={handSlot.Value} target={targetSlot} id={card.Id.Entry}");
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
