using Godot;
using MegaCrit.Sts2.Core.Entities.RestSite;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Runs;

namespace Sts2TasMod;

/// <summary>
/// Rest / shop / treasure proceed. Rest mirrors NRestSiteButton.SelectOption:
/// DisableOptions, await ChooseLocalOption, AfterSelectingOption, then Proceed.
/// </summary>
public static class ScreenAdvance
{
    private static bool _restBusy;

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

    public static string WorldPhase()
    {
        try
        {
            if (Visible(NRestSiteRoom.Instance))
            {
                return "rest";
            }
            if (Visible(NRun.Instance?.MerchantRoom))
            {
                return "shop";
            }
        }
        catch (Exception)
        {
        }
        return "event";
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
            _restBusy = false;
            return false;
        }
        var proceed = rest.ProceedButton;
        if (proceed is { IsEnabled: true })
        {
            proceed.ForceClick();
            _restBusy = false;
            GD.Print("Sts2TasMod rest proceed");
            return true;
        }
        if (Nodes.ClickFirstVisible("NProceedButton"))
        {
            _restBusy = false;
            GD.Print("Sts2TasMod rest proceed leftover");
            return true;
        }
        if (_restBusy)
        {
            GD.Print("Sts2TasMod rest waiting");
            return true;
        }
        if (ClickRestButton(rest))
        {
            _restBusy = true;
            return true;
        }
        var index = FirstEnabledRestOption(rest);
        try
        {
            rest.DisableOptions();
        }
        catch (Exception)
        {
        }
        _restBusy = true;
        CompleteRestOption(rest, index);
        return true;
    }

    private static bool ClickRestButton(NRestSiteRoom rest)
    {
        foreach (var node in Nodes.FindAll(rest, "NRestSiteButton"))
        {
            if (!Nodes.IsShown(node) || !Nodes.Enabled(node))
            {
                continue;
            }
            if (Nodes.ClickControl(node) || Nodes.ForceClickRaw(node))
            {
                GD.Print($"Sts2TasMod rest button {node.Name}");
                return true;
            }
        }
        return false;
    }

    private static int FirstEnabledRestOption(NRestSiteRoom rest)
    {
        try
        {
            var options = rest.Options;
            for (var i = 0; i < options.Count; i++)
            {
                if (options[i].IsEnabled && options[i].OptionId.Equals("HEAL", StringComparison.OrdinalIgnoreCase))
                {
                    return i;
                }
            }
            for (var i = 0; i < options.Count; i++)
            {
                if (options[i].IsEnabled)
                {
                    return i;
                }
            }
        }
        catch (Exception)
        {
        }
        return 0;
    }

    private static async void CompleteRestOption(NRestSiteRoom rest, int index)
    {
        try
        {
            RestSiteOption? option = null;
            try
            {
                if (index >= 0 && index < rest.Options.Count)
                {
                    option = rest.Options[index];
                }
            }
            catch (Exception)
            {
            }
            GD.Print($"Sts2TasMod rest option {index} {option?.OptionId ?? "?"}");
            var sync = RunManager.Instance?.RestSiteSynchronizer;
            if (sync is null)
            {
                _restBusy = false;
                return;
            }
            var success = await sync.ChooseLocalOption(index);
            if (success && option is not null)
            {
                rest.AfterSelectingOption(option);
                GD.Print($"Sts2TasMod rest AfterSelectingOption {option.OptionId}");
            }
            else
            {
                rest.EnableOptions();
                _restBusy = false;
                GD.Print("Sts2TasMod rest option failed");
            }
        }
        catch (Exception ex)
        {
            GD.PrintErr($"Sts2TasMod rest option: {ex.Message}");
            try
            {
                rest.EnableOptions();
            }
            catch (Exception)
            {
            }
            _restBusy = false;
        }
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
