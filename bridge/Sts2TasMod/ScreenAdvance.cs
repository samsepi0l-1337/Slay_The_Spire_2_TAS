using Godot;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Runs;

namespace Sts2TasMod;

/// <summary>
/// Rest / shop / treasure / finished-event proceed, verified against
/// STS2 AutoSlay and the public CLI mod handlers (ForceClick NProceedButton,
/// NEventRoom.Proceed, RestSiteSynchronizer.ChooseLocalOption).
/// </summary>
public static class ScreenAdvance
{
    public static bool TryWorld()
    {
        try
        {
            if (TryRest())
            {
                return true;
            }
            if (TryTreasure())
            {
                return true;
            }
            if (TryShop())
            {
                return true;
            }
        }
        catch (Exception ex)
        {
            GD.PrintErr($"Sts2TasMod ScreenAdvance: {ex.Message}");
        }
        return false;
    }

    public static bool InWorldRoom()
    {
        try
        {
            if (Visible(NRestSiteRoom.Instance))
            {
                return true;
            }
            if (Visible(NRun.Instance?.TreasureRoom))
            {
                return true;
            }
            if (Visible(NRun.Instance?.MerchantRoom))
            {
                return true;
            }
        }
        catch (Exception)
        {
            return false;
        }
        return false;
    }

    private static bool Visible(Node? node)
    {
        return node is CanvasItem canvas && canvas.IsInsideTree() && canvas.IsVisibleInTree();
    }

    private static bool TryRest()
    {
        var rest = NRestSiteRoom.Instance;
        if (rest is null || !Visible(rest))
        {
            return false;
        }
        var proceed = rest.ProceedButton;
        if (proceed is { IsEnabled: true })
        {
            proceed.ForceClick();
            GD.Print("Sts2TasMod rest proceed");
            return true;
        }
        _ = RunManager.Instance?.RestSiteSynchronizer.ChooseLocalOption(0);
        GD.Print("Sts2TasMod rest option 0 (HEAL)");
        return true;
    }

    private static bool TryTreasure()
    {
        var treasure = NRun.Instance?.TreasureRoom;
        if (treasure is null || !Visible(treasure))
        {
            return false;
        }
        treasure.ProceedButton?.ForceClick();
        GD.Print("Sts2TasMod treasure proceed");
        return true;
    }

    private static bool TryShop()
    {
        var shop = NRun.Instance?.MerchantRoom;
        if (shop is null || !Visible(shop))
        {
            return false;
        }
        shop.ProceedButton?.ForceClick();
        GD.Print("Sts2TasMod shop proceed");
        return true;
    }
}
