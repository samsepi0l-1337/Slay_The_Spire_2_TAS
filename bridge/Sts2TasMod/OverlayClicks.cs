using Godot;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;

namespace Sts2TasMod;

internal static class OverlayClicks
{
    internal static bool HasRewardUi()
    {
        var root = Nodes.Root();
        foreach (var name in new[]
                 {
                     "NCardRewardSelectionScreen", "NCardSelectionScreen", "NCardGridSelectionScreen",
                     "NSimpleCardSelectScreen", "NDeckCardSelectScreen", "NDeckUpgradeSelectScreen"
                 })
        {
            if (Nodes.FindType(root, name) is Node node && Nodes.IsShown(node))
            {
                return true;
            }
        }
        if (RunFlow.MapIsOpen())
        {
            return false;
        }
        return Nodes.FindType(root, "NRewardsScreen") is Node rewards && Nodes.IsShown(rewards);
    }

    internal static void LogOverlay()
    {
        try
        {
            if (NOverlayStack.Instance?.Peek() is Node overlay)
            {
                GD.Print($"Sts2TasMod overlay={overlay.GetType().Name}");
            }
        }
        catch (Exception)
        {
        }
    }

    internal static bool ClickAnyCardHolder()
    {
        var root = Nodes.Root();
        foreach (var name in new[] { "NCardHolder", "NGridCardHolder" })
        {
            foreach (var node in Nodes.FindAll(root, name))
            {
                if (node is NCardHolder holder && holder.CardModel is not null && Nodes.IsShown(holder))
                {
                    holder.EmitSignal(NCardHolder.SignalName.Pressed, holder);
                    GD.Print($"Sts2TasMod grid card {holder.CardModel.Id.Entry}");
                    return true;
                }
            }
        }
        return false;
    }

    private static readonly HashSet<string> ClickedRewards = [];

    internal static void ClaimRewards()
    {
        LogOverlay();
        try
        {
            if (ClickAnyCardHolder())
            {
                return;
            }
            if (Nodes.ClickFirstVisible("NConfirmButton"))
            {
                GD.Print("Sts2TasMod grid confirm");
                return;
            }
            var root = Nodes.Root();
            var cardScreen = Nodes.FindType(root, "NCardRewardSelectionScreen");
            if (cardScreen is not null && Nodes.IsShown(cardScreen))
            {
                _ = PickFirstRewardCard(cardScreen) || SkipRewardCards(cardScreen);
                return;
            }
            if (ClickUnclaimedReward())
            {
                return;
            }
            ClickedRewards.Clear();
            if (ClickProceed())
            {
                return;
            }
            Nodes.ClickNamed(root, "ProceedButton");
        }
        catch (Exception ex)
        {
            GD.PrintErr($"Sts2TasMod ClaimRewards: {ex.Message}");
            ClickedRewards.Clear();
            _ = ClickProceed();
        }
    }

    private static bool ClickUnclaimedReward()
    {
        foreach (var node in Nodes.FindAll(Nodes.Root(), "NRewardButton"))
        {
            var id = $"{node.GetType().Name}:{node.Name}:{node.GetInstanceId()}";
            if (ClickedRewards.Contains(id) || !Nodes.IsShown(node))
            {
                continue;
            }
            if (!Nodes.ClickControl(node))
            {
                continue;
            }
            ClickedRewards.Add(id);
            GD.Print($"Sts2TasMod claim {id}");
            return true;
        }
        return false;
    }

    private static bool ClickProceed()
    {
        if (Nodes.ClickFirstVisible("NProceedButton") || Nodes.ClickFirstShown("NProceedButton"))
        {
            GD.Print("Sts2TasMod reward proceed");
            return true;
        }
        return false;
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
