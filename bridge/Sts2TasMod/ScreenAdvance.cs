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
            if (NRestSiteRoom.Instance is { } rest && rest.IsInsideTree())
            {
                return true;
            }
            if (NEventRoom.Instance is { } ev && ev.IsInsideTree())
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

    private static bool TryRest()
    {
        var rest = NRestSiteRoom.Instance;
        if (rest is null || !rest.IsInsideTree())
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
        _ = RunManager.Instance.RestSiteSynchronizer.ChooseLocalOption(0);
        GD.Print("Sts2TasMod rest option 0 (HEAL)");
        return true;
    }

    private static bool TryTreasure()
    {
        var treasure = NRun.Instance?.TreasureRoom;
        if (treasure is null || !treasure.IsInsideTree())
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
        if (shop is null || !shop.IsInsideTree())
        {
            return false;
        }
        shop.ProceedButton?.ForceClick();
        GD.Print("Sts2TasMod shop proceed");
        return true;
    }
}
