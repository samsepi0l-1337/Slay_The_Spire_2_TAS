using System.Reflection;
using System.Threading;
using Godot;
using MegaCrit.Sts2.Core.AutoSlay;
using MegaCrit.Sts2.Core.AutoSlay.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
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
        if (!OverlayClicks.HasRewardUi())
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
        if (AdvanceAncientDialogue(room))
        {
            return;
        }
        OverlayClicks.LogOverlay();
        if (OverlayClicks.HasRewardUi() || OverlayClicks.ClickAnyCardHolder())
        {
            OverlayClicks.ClaimRewards();
            return;
        }
        var model = EventModelOf(room);
        var finished = model?.IsFinished == true;
        var buttons = room.Layout?.OptionButtons?.Cast<Node>().ToList() ?? [];
        if (buttons.Count == 0)
        {
            buttons = Nodes.FindAll(room, "NEventOptionButton").ToList();
        }
        GD.Print($"Sts2TasMod event finished={finished} buttons={buttons.Count} options={model?.CurrentOptions.Count}");
        if (!finished && ClickChoice(room, buttons, slot))
        {
            _lastEventClickMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            return;
        }
        if (DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() - _lastEventClickMs < 3000)
        {
            GD.Print("Sts2TasMod event settling");
            return;
        }
        if (!finished && ClickModelOption(room, model, slot + _stuckOption))
        {
            _stuckOption += 1;
            _lastEventClickMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            return;
        }
        if (ClickProceedButtons(room, buttons))
        {
            LeaveFinished("clicked IsProceed");
            return;
        }
        if (finished || (model?.CurrentOptions.Count ?? 0) == 0)
        {
            LeaveFinished("no proceed button");
            return;
        }
        if (Nodes.ClickFirstVisible("NConfirmButton") || Nodes.ClickFirstVisible("NProceedButton"))
        {
            GD.Print("Sts2TasMod event confirm/proceed overlay");
            return;
        }
        GD.Print("Sts2TasMod event waiting (not finished)");
    }

    private static bool _leaving;
    private static long _lastEventClickMs;
    private static int _stuckOption;

    private static async void LeaveFinished(string reason)
    {
        if (_leaving)
        {
            return;
        }
        _leaving = true;
        _stuckOption = 0;
        try
        {
            await ClickEventProceedIfNeeded();
            GD.Print($"Sts2TasMod await NEventRoom.Proceed ({reason})");
            await NEventRoom.Proceed();
            var map = MegaCrit.Sts2.Core.Nodes.Screens.Map.NMapScreen.Instance;
            map?.SetTravelEnabled(true);
            map?.Open(false);
            if (NEventRoom.Instance is CanvasItem canvas)
            {
                canvas.Visible = false;
            }
            GD.Print($"Sts2TasMod NEventRoom.Proceed completed mapOpen={map?.IsOpen}");
        }
        catch (Exception ex)
        {
            GD.PrintErr($"Sts2TasMod leave failed: {ex.Message}");
        }
        finally
        {
            _leaving = false;
        }
    }

    private static async Task ClickEventProceedIfNeeded()
    {
        try
        {
            var method = typeof(AutoSlayer).GetMethod(
                "ClickEventProceedIfNeeded",
                BindingFlags.Instance | BindingFlags.NonPublic);
            if (method is null)
            {
                return;
            }
            if (method.Invoke(new AutoSlayer(), [CancellationToken.None]) is not Task task)
            {
                return;
            }
            GD.Print("Sts2TasMod ClickEventProceedIfNeeded");
            var done = await Task.WhenAny(task, Task.Delay(4000));
            GD.Print(done == task
                ? "Sts2TasMod ClickEventProceedIfNeeded done"
                : "Sts2TasMod ClickEventProceedIfNeeded timeout");
        }
        catch (Exception ex)
        {
            GD.PrintErr($"Sts2TasMod ClickEventProceedIfNeeded: {ex.InnerException?.Message ?? ex.Message}");
        }
    }

    private static bool ClickModelOption(NEventRoom room, EventModel? model, int slot)
    {
        if (model is null || model.CurrentOptions.Count == 0)
        {
            return false;
        }
        var index = Math.Clamp(slot, 0, model.CurrentOptions.Count - 1);
        try
        {
            room.OptionButtonClicked(model.CurrentOptions[index], index);
            GD.Print($"Sts2TasMod model option {index}/{model.CurrentOptions.Count}");
            return true;
        }
        catch (Exception ex)
        {
            GD.PrintErr($"Sts2TasMod model option: {ex.Message}");
            return false;
        }
    }

    private static bool ClickChoice(NEventRoom room, List<Node> buttons, int slot)
    {
        var choices = buttons
            .Select((node, index) => (node, index))
            .Where(pair => !IsLocked(pair.node) && !IsProceed(pair.node))
            .ToList();
        if (choices.Count == 0)
        {
            return false;
        }
        var pick = choices[Math.Clamp(slot, 0, choices.Count - 1)];
        return ClickOption(room, pick.node, pick.index, $"option {pick.index}/{buttons.Count}");
    }

    private static bool ClickProceedButtons(NEventRoom room, List<Node> buttons)
    {
        foreach (var (node, index) in buttons.Select((node, index) => (node, index)))
        {
            if (IsProceed(node) && ClickOption(room, node, index, $"IsProceed {index}"))
            {
                return true;
            }
        }
        foreach (var node in Nodes.FindAll(room, "NEventOptionButton"))
        {
            if (IsProceed(node) && ClickOption(room, node, 0, $"leftover {node.Name}"))
            {
                return true;
            }
        }
        return false;
    }

    private static bool ClickOption(NEventRoom room, Node node, int index, string label)
    {
        try
        {
            if (node is NEventOptionButton optionButton)
            {
                optionButton.EnableButton();
                room.OptionButtonClicked(optionButton.Option, index);
            }
        }
        catch (Exception ex)
        {
            GD.PrintErr($"Sts2TasMod OptionButtonClicked: {ex.Message}");
        }
        if (node is not NClickableControl clickable)
        {
            return Nodes.ClickControl(node);
        }
        try
        {
            _ = UiHelper.Click(clickable);
            GD.Print($"Sts2TasMod UiHelper.Click {label}");
            return true;
        }
        catch (Exception ex)
        {
            GD.PrintErr($"Sts2TasMod UiHelper.Click failed: {ex.Message}");
        }
        clickable.ForceClick();
        GD.Print($"Sts2TasMod ForceClick {label}");
        return true;
    }

    private static EventModel? EventModelOf(NEventRoom room)
    {
        return typeof(NEventRoom)
            .GetField("_event", BindingFlags.NonPublic | BindingFlags.Instance)
            ?.GetValue(room) as EventModel;
    }

    private static bool IsProceed(Node node)
    {
        var option = node.GetType().GetProperty("Option")?.GetValue(node);
        return option?.GetType().GetProperty("IsProceed")?.GetValue(option) is true;
    }

    private static bool IsLocked(Node node)
    {
        var option = node.GetType().GetProperty("Option")?.GetValue(node);
        return option?.GetType().GetProperty("IsLocked")?.GetValue(option) is true;
    }

    private static bool AdvanceAncientDialogue(NEventRoom room)
    {
        if (room.Layout is not NAncientEventLayout ancient)
        {
            return false;
        }
        var onLast = typeof(NAncientEventLayout)
            .GetProperty("IsDialogueOnLastLine", BindingFlags.NonPublic | BindingFlags.Instance)
            ?.GetValue(ancient) as bool? ?? true;
        if (onLast)
        {
            return false;
        }
        var hitbox = ancient.GetNodeOrNull<NClickableControl>("%DialogueHitbox");
        if (hitbox is null || !hitbox.IsVisibleInTree() || !hitbox.IsEnabled)
        {
            return false;
        }
        try
        {
            hitbox.ForceClick();
            GD.Print("Sts2TasMod advance Ancient dialogue");
            return true;
        }
        catch (Exception ex)
        {
            GD.PrintErr($"Sts2TasMod dialogue click skipped: {ex.Message}");
            return false;
        }
    }
}
