using System.Reflection;
using Godot;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.Rooms;

namespace Sts2TasMod;

internal static class EventReward
{
    internal static List<Dictionary<string, object?>> EventActions()
    {
        var actions = new List<Dictionary<string, object?>>();
        if (!RunFlow.InEventRoom())
        {
            return actions;
        }
        var count = 1;
        try
        {
            var buttons = NEventRoom.Instance!.Layout?.OptionButtons;
            if (buttons is not null)
            {
                count = Math.Max(buttons.Count(), 1);
            }
        }
        catch (Exception)
        {
            count = 1;
        }
        for (var slot = 0; slot < count; slot++)
        {
            actions.Add(new Dictionary<string, object?>
            {
                ["action_type"] = "choose_event_option",
                ["args"] = new Dictionary<string, int> { ["choice_slot"] = slot }
            });
        }
        return actions;
    }

    internal static List<Dictionary<string, object?>> RewardActions()
    {
        if (RunFlow.InEventRoom())
        {
            return [];
        }
        var root = Nodes.Root();
        var cards = Nodes.FindType(root, "NCardRewardSelectionScreen");
        var rewards = Nodes.FindType(root, "NRewardsScreen");
        if ((cards is null || !Nodes.IsShown(cards)) && (rewards is null || !Nodes.IsShown(rewards)))
        {
            return [];
        }
        return
        [
            new Dictionary<string, object?>
            {
                ["action_type"] = "choose_reward",
                ["args"] = new Dictionary<string, int> { ["choice_slot"] = 0 }
            }
        ];
    }

    internal static void ChooseEvent(int slot)
    {
        var room = NEventRoom.Instance;
        if (room is null || !room.IsInsideTree())
        {
            return;
        }
        if (AdvanceAncientDialogue(room, force: false))
        {
            return;
        }
        var model = typeof(NEventRoom).GetField("_event", BindingFlags.NonPublic | BindingFlags.Instance)?.GetValue(room) as EventModel;
        if (model is { IsFinished: true })
        {
            AwaitProceed("finished");
            return;
        }
        var buttons = room.Layout?.OptionButtons?.ToList();
        if (buttons is { Count: > 0 })
        {
            var index = Math.Clamp(slot, 0, buttons.Count - 1);
            if (buttons[index] is NClickableControl clickable)
            {
                clickable.ForceClick();
                GD.Print($"Sts2TasMod ForceClick option {index}/{buttons.Count}");
                return;
            }
            Nodes.ClickControl(buttons[index]);
            return;
        }
        if (AdvanceAncientDialogue(room, force: true))
        {
            return;
        }
        AwaitProceed("no buttons");
    }

    private static bool _proceeding;

    private static async void AwaitProceed(string reason)
    {
        if (_proceeding)
        {
            return;
        }
        _proceeding = true;
        try
        {
            GD.Print($"Sts2TasMod await NEventRoom.Proceed ({reason})");
            await NEventRoom.Proceed();
            GD.Print("Sts2TasMod NEventRoom.Proceed completed");
        }
        catch (Exception ex)
        {
            GD.PrintErr($"Sts2TasMod Proceed failed: {ex.Message}");
        }
        finally
        {
            _proceeding = false;
        }
    }

    private static bool AdvanceAncientDialogue(NEventRoom room, bool force)
    {
        if (room.Layout is not NAncientEventLayout ancient)
        {
            return false;
        }
        var onLast = typeof(NAncientEventLayout)
            .GetProperty("IsDialogueOnLastLine", BindingFlags.NonPublic | BindingFlags.Instance)
            ?.GetValue(ancient) as bool? ?? false;
        if (onLast && !force)
        {
            return false;
        }
        var hitbox = ancient.GetNodeOrNull<NClickableControl>("%DialogueHitbox");
        if (hitbox is null)
        {
            return false;
        }
        hitbox.ForceClick();
        GD.Print(force ? "Sts2TasMod advance Ancient dialogue (fallback)" : "Sts2TasMod advance Ancient dialogue");
        return true;
    }

    internal static void ClaimRewards()
    {
        var root = Nodes.Root();
        var cardScreen = Nodes.FindType(root, "NCardRewardSelectionScreen");
        if (cardScreen is not null && Nodes.IsShown(cardScreen))
        {
            if (PickFirstRewardCard(cardScreen)) { return; }
            if (SkipRewardCards(cardScreen)) { return; }
            return;
        }
        if (Nodes.ClickFirstVisible("NRewardButton")) { return; }
        if (Nodes.ClickFirstVisible("NProceedButton")) { return; }
        Nodes.ClickNamed(root, "ProceedButton");
    }

    private static bool PickFirstRewardCard(Node screen)
    {
        var row = screen.GetNodeOrNull<Control>("UI/CardRow");
        if (row is null)
        {
            return false;
        }
        foreach (var child in row.GetChildren())
        {
            if (child is NCardHolder holder && holder.CardModel is not null && Nodes.IsShown(holder))
            {
                holder.EmitSignal(NCardHolder.SignalName.Pressed, holder);
                GD.Print($"Sts2TasMod selected reward {holder.CardModel.Id.Entry}");
                return true;
            }
        }
        return false;
    }

    private static bool SkipRewardCards(Node screen)
    {
        var alts = screen.GetNodeOrNull<Control>("UI/RewardAlternatives");
        if (alts is not null)
        {
            foreach (var child in alts.GetChildren())
            {
                if (Nodes.ClickControl(child))
                {
                    return true;
                }
            }
        }
        return Nodes.ClickFirstVisible("NChoiceSelectionSkipButton");
    }
}
