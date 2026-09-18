using System.Reflection;
using Godot;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;

namespace Sts2TasMod;

internal static class OverlayClicks
{
    private static readonly string[] SelectScreens =
    [
        "NCardRewardSelectionScreen", "NCardSelectionScreen", "NCardGridSelectionScreen",
        "NSimpleCardSelectScreen", "NDeckCardSelectScreen", "NDeckUpgradeSelectScreen",
        "NDeckTransformSelectScreen"
    ];

    private static readonly HashSet<string> ClickedRewards = [];
    private static string? _gridPick;
    private static string? _gridOverlay;

    internal static bool HasRewardUi()
    {
        var overlay = PeekName();
        if (overlay is not null && IsSelectOverlay(overlay))
        {
            return true;
        }
        var root = Nodes.Root();
        foreach (var name in SelectScreens)
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
        var overlay = PeekName();
        if (overlay is not null)
        {
            GD.Print($"Sts2TasMod overlay={overlay}");
        }
    }

    internal static string? PeekName()
    {
        try
        {
            return NOverlayStack.Instance?.Peek() is Node overlay ? overlay.GetType().Name : null;
        }
        catch (Exception)
        {
            return null;
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
                    _gridPick = holder.CardModel.Id.Entry;
                    _gridOverlay = PeekName();
                    GD.Print($"Sts2TasMod grid card {_gridPick}");
                    return true;
                }
            }
        }
        return false;
    }

    internal static void ClaimRewards(int? slot = null)
    {
        LogOverlay();
        try
        {
            var overlay = PeekName();
            if (overlay != _gridOverlay)
            {
                _gridPick = null;
                _gridOverlay = overlay;
            }
            if (slot == 1 && ClickSkip())
            {
                return;
            }
            if (IsGridSelect(overlay))
            {
                ClickGridThenConfirm();
                return;
            }
            if (ClickAnyCardHolder())
            {
                return;
            }
            var root = Nodes.Root();
            var cardScreen = Nodes.FindType(root, "NCardRewardSelectionScreen");
            if (cardScreen is not null && Nodes.IsShown(cardScreen))
            {
                if (slot == 1)
                {
                    _ = SkipRewardCards(cardScreen);
                    return;
                }
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
            _gridPick = null;
            _ = ClickProceed();
        }
    }

    private static bool IsSelectOverlay(string name)
    {
        return SelectScreens.Contains(name) || name.Contains("SelectScreen", StringComparison.Ordinal);
    }

    private static bool IsGridSelect(string? name)
    {
        if (string.IsNullOrEmpty(name))
        {
            return false;
        }
        return name.Contains("Grid", StringComparison.Ordinal)
               || name.Contains("Deck", StringComparison.Ordinal)
               || name.Contains("SimpleCardSelect", StringComparison.Ordinal);
    }

    private static void ClickGridThenConfirm()
    {
        if (_gridPick is not null)
        {
            if (ClickGridConfirm())
            {
                GD.Print($"Sts2TasMod grid confirm {_gridPick}");
                _gridPick = null;
                return;
            }
            GD.Print($"Sts2TasMod wait confirm {_gridPick}");
            return;
        }
        if (ClickAnyCardHolder())
        {
            return;
        }
        if (ClickGridConfirm())
        {
            GD.Print("Sts2TasMod grid confirm leftover");
        }
    }

    private static bool ClickGridConfirm()
    {
        Node? overlay = null;
        try
        {
            overlay = NOverlayStack.Instance?.Peek() as Node;
        }
        catch (Exception)
        {
        }
        if (overlay is not null)
        {
            foreach (var name in new[]
                     {
                         "_previewConfirmButton", "_singlePreviewConfirmButton",
                         "_multiPreviewConfirmButton", "_confirmButton"
                     })
            {
                if (Field(overlay, name) is Node button
                    && (Nodes.ClickControl(button) || Nodes.ForceClickRaw(button)))
                {
                    return true;
                }
            }
            try
            {
                var named = overlay.GetNodeOrNull("%Confirm");
                if (named is not null && (Nodes.ClickControl(named) || Nodes.ForceClickRaw(named)))
                {
                    return true;
                }
            }
            catch (Exception)
            {
            }
            foreach (var node in Nodes.FindAll(overlay, "NConfirmButton"))
            {
                if (node.Name.ToString().Contains("SelectMode", StringComparison.Ordinal))
                {
                    continue;
                }
                if (Nodes.ClickControl(node) || Nodes.ForceClickRaw(node))
                {
                    return true;
                }
            }
        }
        return false;
    }

    private static object? Field(object obj, string name)
    {
        for (var type = obj.GetType(); type is not null; type = type.BaseType)
        {
            var field = type.GetField(name, BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
            if (field is not null)
            {
                try
                {
                    return field.GetValue(obj);
                }
                catch (Exception)
                {
                    return null;
                }
            }
        }
        return null;
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
                if (Nodes.ClickControl(child) || Nodes.ForceClickRaw(child))
                {
                    GD.Print($"Sts2TasMod skip {child.Name}");
                    return true;
                }
            }
        }
        return ClickSkip();
    }

    internal static bool ClickSkip()
    {
        foreach (var name in new[]
                 {
                     "NCardRewardAlternativeButton", "NChoiceSelectionSkipButton", "NSkipButton"
                 })
        {
            if (Nodes.ClickFirstVisible(name) || Nodes.ClickFirstShown(name))
            {
                GD.Print($"Sts2TasMod skip {name}");
                return true;
            }
        }
        Node? overlay = null;
        try
        {
            overlay = NOverlayStack.Instance?.Peek() as Node;
        }
        catch (Exception)
        {
        }
        if (overlay is null)
        {
            return false;
        }
        try
        {
            var close = overlay.GetNodeOrNull("%Close");
            if (close is not null && (Nodes.ClickControl(close) || Nodes.ForceClickRaw(close)))
            {
                GD.Print("Sts2TasMod skip close");
                return true;
            }
        }
        catch (Exception)
        {
        }
        return false;
    }
}
