using Godot;
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

    private static string _pickedPath = "";

    internal static void ChooseEvent(int slot)
    {
        var options = EnabledOptions().Where(option => option.GetPath() != _pickedPath).ToList();
        if (options.Count > 0)
        {
            var proceed = options.FirstOrDefault(IsProceedOption);
            var pick = proceed ?? options[Math.Clamp(slot, 0, options.Count - 1)];
            if (SelectOption(pick))
            {
                _pickedPath = pick.GetPath();
                GD.Print($"Sts2TasMod event select {pick.Name} n={options.Count} proceed={IsProceedOption(pick)}");
                return;
            }
        }
        _pickedPath = "";
        if (ClickRoomProceed())
        {
            return;
        }
        try
        {
            _ = NEventRoom.Proceed();
            GD.Print("Sts2TasMod event proceed");
        }
        catch (Exception ex)
        {
            GD.PrintErr($"Sts2TasMod event proceed failed: {ex.Message}");
        }
    }

    private static List<Node> EnabledOptions()
    {
        var found = new List<Node>();
        var room = NEventRoom.Instance;
        if (room is null || !room.IsInsideTree())
        {
            return found;
        }
        foreach (var node in Nodes.FindAll(room, "NEventOptionButton"))
        {
            if (!Nodes.IsShown(node) || !Nodes.Enabled(node) || IsLockedOption(node))
            {
                continue;
            }
            found.Add(node);
        }
        return found;
    }

    private static bool IsLockedOption(Node button)
    {
        var option = button.GetType().GetProperty("Option")?.GetValue(button);
        return option?.GetType().GetProperty("IsLocked")?.GetValue(option) is true;
    }

    private static bool IsProceedOption(Node button)
    {
        var option = button.GetType().GetProperty("Option")?.GetValue(button);
        return option?.GetType().GetProperty("IsProceed")?.GetValue(option) is true;
    }

    private static bool SelectOption(Node button)
    {
        var room = NEventRoom.Instance;
        var option = button.GetType().GetProperty("Option")?.GetValue(button);
        if (room is not null && InvokeMatching(room, "OptionButtonClicked", button, option))
        {
            return true;
        }
        if (room is not null && InvokeMatching(room, "ChooseOptionForEvent", button, option))
        {
            return true;
        }
        var chosen = option?.GetType().GetMethod("Chosen", Type.EmptyTypes);
        if (chosen is not null)
        {
            try
            {
                chosen.Invoke(option, null);
                return true;
            }
            catch (Exception ex)
            {
                GD.PrintErr($"Sts2TasMod Chosen: {ex.InnerException?.Message ?? ex.Message}");
            }
        }
        return Nodes.ClickControl(button);
    }

    private static bool InvokeMatching(object target, string name, params object?[] candidates)
    {
        foreach (var method in target.GetType().GetMethods().Where(method => method.Name == name))
        {
            var parameters = method.GetParameters();
            object?[]? args = parameters.Length switch
            {
                0 => [],
                1 => candidates.FirstOrDefault(candidate => candidate is not null && parameters[0].ParameterType.IsInstanceOfType(candidate)) is { } match
                    ? [match]
                    : null,
                _ => null
            };
            if (args is null)
            {
                continue;
            }
            try
            {
                method.Invoke(target, args);
                GD.Print($"Sts2TasMod invoked {name}");
                return true;
            }
            catch (Exception ex)
            {
                GD.PrintErr($"Sts2TasMod {name}: {ex.InnerException?.Message ?? ex.Message}");
            }
        }
        return false;
    }

    private static bool ClickRoomProceed()
    {
        var room = NEventRoom.Instance;
        if (room is not null)
        {
            foreach (var name in new[] { "TryEnableProceedButton", "ShowProceedButton", "CreateProceedOption" })
            {
                InvokeMatching(room, name);
            }
            var proceed = room.GetType().GetProperty("ProceedButton")?.GetValue(room) as Node;
            if (Nodes.ClickControl(proceed) || Nodes.ForceClickRaw(proceed))
            {
                GD.Print("Sts2TasMod event ProceedButton");
                return true;
            }
        }
        if (Nodes.ClickFirstVisible("NProceedButton") || Nodes.ClickFirstShown("NProceedButton"))
        {
            GD.Print("Sts2TasMod event proceed button");
            return true;
        }
        return false;
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
