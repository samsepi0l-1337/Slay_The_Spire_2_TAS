using Godot;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.CommonUi;

namespace Sts2TasMod;

internal static class HandSelect
{
    private static int _lastSlot = -1;

    internal static bool Active()
    {
        try
        {
            return NPlayerHand.Instance is { IsInCardSelection: true };
        }
        catch (Exception)
        {
            return false;
        }
    }

    internal static bool Apply(int? slot)
    {
        try
        {
            var hand = NPlayerHand.Instance;
            if (hand is not { IsInCardSelection: true })
            {
                _lastSlot = -1;
                return false;
            }
            if (_lastSlot >= 0 && ClickConfirm(hand))
            {
                return true;
            }
            var holders = hand.ActiveHolders;
            if (holders is null || holders.Count == 0)
            {
                return ClickConfirm(hand);
            }
            var index = Math.Clamp(slot ?? 0, 0, holders.Count - 1);
            var holder = holders[index];
            holder.EmitSignal(NCardHolder.SignalName.Pressed, holder);
            _lastSlot = index;
            GD.Print($"Sts2TasMod hand select slot={index} {holder.CardNode?.Model?.Id.Entry}");
            return true;
        }
        catch (Exception ex)
        {
            GD.PrintErr($"Sts2TasMod hand select: {ex.Message}");
            return false;
        }
    }

    private static bool ClickConfirm(NPlayerHand hand)
    {
        try
        {
            var confirm = hand.GetNodeOrNull<NConfirmButton>("%SelectModeConfirmButton");
            if (confirm is null)
            {
                return false;
            }
            confirm.ForceClick();
            _lastSlot = -1;
            GD.Print("Sts2TasMod hand select confirm");
            return true;
        }
        catch (Exception ex)
        {
            GD.PrintErr($"Sts2TasMod hand confirm: {ex.Message}");
            return false;
        }
    }
}
