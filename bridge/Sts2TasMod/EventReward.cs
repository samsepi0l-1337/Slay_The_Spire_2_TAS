using Godot;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.Events;

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
        if (Nodes.ClickFirstShown("NEventOptionButton"))
        {
            GD.Print("Sts2TasMod event option button");
            return;
        }
        if (NEventRoom.Instance is { } room && room.IsInsideTree())
        {
            try
            {
                var buttons = room.Layout?.OptionButtons?.ToList();
                if (buttons is { Count: > 0 })
                {
                    var index = Math.Clamp(slot, 0, buttons.Count - 1);
                    if (Nodes.ForceClickRaw(buttons[index]) || Nodes.ForceClickRaw(buttons[0]))
                    {
                        GD.Print($"Sts2TasMod event option {index}");
                        return;
                    }
                }
                var hitbox = room.GetNodeOrNull<Node>("%DialogueHitbox") ?? room.FindChild("DialogueHitbox", true, false);
                if (Nodes.ForceClickRaw(hitbox) || Nodes.ClickFirstShown("NAncientDialogueHitbox"))
                {
                    GD.Print("Sts2TasMod DialogueHitbox");
                    return;
                }
                _ = NEventRoom.Proceed();
                GD.Print("Sts2TasMod event proceed");
                return;
            }
            catch (Exception ex)
            {
                GD.PrintErr($"Sts2TasMod event click failed: {ex.Message}");
            }
        }
        if (Nodes.ClickFirstShown("NAncientDialogueHitbox"))
        {
            return;
        }
        Nodes.ClickFirstVisible("NProceedButton");
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
